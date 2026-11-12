"""Small standard-library reporting primitives for outcome experiments."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any, Hashable, Iterable, Protocol

from memory_fabric.adapters.ollama import CallRecord, OllamaError
from memory_fabric.agent_outcomes import AgentObservation, AgentStep, EpisodeOutcome
from .stats import paired_bootstrap, sign_test_p


class RealAgentStatus(StrEnum):
    PASS = "PASS"
    NOT_RUN = "REAL_AGENT_NOT_RUN"
    FAIL = "FAIL"


class RealAgentAdapter(Protocol):
    model: str
    actor_id: str
    calls: tuple[CallRecord, ...]

    def next_step(self, observation: AgentObservation) -> AgentStep: ...


@dataclass(frozen=True)
class RealAgentRunReport:
    """One model-only attempt, kept separate from scripted outcome reports."""

    task_id: str
    status: RealAgentStatus
    reason: str
    model: str | None
    model_calls: int
    model_tokens: int
    step: AgentStep | None = field(default=None, repr=False)
    schema_id: str = "memory-fabric.real-agent-report.v1"

    def to_dict(self) -> dict[str, Any]:
        report: dict[str, Any] = {
            "schema_id": self.schema_id,
            "population": "REAL_AGENT",
            "task_id": self.task_id,
            "status": self.status.value,
            "reason": self.reason,
            "model": self.model,
            "model_calls": self.model_calls,
            "model_tokens": self.model_tokens,
        }
        if self.step is not None:
            report["step"] = self.step.to_dict()
        return report

    def canonical_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"),
                          allow_nan=False)


def run_real_agent_gate(
    adapter: RealAgentAdapter,
    observation: AgentObservation,
) -> RealAgentRunReport:
    """Pass only after a new Ollama call record and validated AgentStep exist.

    An unavailable server is an explicit no-run result. This path has no
    scripted actor fallback, and its report is independent of `canonical_report`.
    """
    calls_before = tuple(adapter.calls)
    try:
        step = adapter.next_step(observation)
    except OllamaError:
        return RealAgentRunReport(
            task_id=observation.task_id,
            status=RealAgentStatus.NOT_RUN,
            reason="model_unavailable",
            model=adapter.model,
            model_calls=0,
            model_tokens=0,
        )
    except Exception:  # noqa: BLE001 - produce a stable, content-safe gate result
        calls_after = tuple(adapter.calls)
        new_calls = calls_after[len(calls_before):]
        recorded = [call for call in new_calls if isinstance(call, CallRecord)]
        return RealAgentRunReport(
            task_id=observation.task_id,
            status=RealAgentStatus.FAIL,
            reason="inference_or_step_validation_failed",
            model=recorded[-1].model if recorded else adapter.model,
            model_calls=len(recorded),
            model_tokens=sum(call.tokens for call in recorded),
        )

    calls_after = tuple(adapter.calls)
    new_calls = calls_after[len(calls_before):]
    if not new_calls or any(not isinstance(call, CallRecord) for call in new_calls):
        return RealAgentRunReport(
            task_id=observation.task_id,
            status=RealAgentStatus.NOT_RUN,
            reason="no_recorded_inference",
            model=adapter.model,
            model_calls=0,
            model_tokens=0,
        )
    records = [call for call in new_calls if isinstance(call, CallRecord)]
    permitted = (step.intent == "abstain" or
                 (isinstance(step.arguments.get("tool"), str)
                  and step.arguments["tool"] in observation.permitted_tools)) \
        if isinstance(step, AgentStep) else False
    if (not isinstance(step, AgentStep) or step.task_id != observation.task_id
            or step.actor_id != adapter.actor_id or not permitted):
        return RealAgentRunReport(
            task_id=observation.task_id,
            status=RealAgentStatus.FAIL,
            reason="invalid_agent_step",
            model=records[-1].model,
            model_calls=len(records),
            model_tokens=sum(call.tokens for call in records),
        )
    return RealAgentRunReport(
        task_id=observation.task_id,
        status=RealAgentStatus.PASS,
        reason="completed_inference",
        model=records[-1].model,
        model_calls=len(records),
        model_tokens=sum(call.tokens for call in records),
        step=step,
    )


def zero_event_upper_bound(events: int, trials: int, confidence: float = 0.95) -> float:
    """One-sided exact binomial upper bound; for zero events use 1-(1-CI)^(1/n)."""
    if trials <= 0 or events < 0 or events > trials or not 0 < confidence < 1:
        raise ValueError("require trials > 0, 0 <= events <= trials, and 0 < confidence < 1")
    if events == 0:
        return 1.0 - (1.0 - confidence) ** (1.0 / trials)
    # Invert P_p(X <= events) = 1-confidence by bounded bisection.
    target = 1.0 - confidence

    def lower_tail(probability: float) -> float:
        terms = [math.comb(trials, k) * probability**k * (1 - probability)**(trials-k)
                 for k in range(events + 1)]
        return min(1.0, sum(terms))

    low, high = 0.0, 1.0
    for _ in range(80):
        mid = (low + high) / 2
        if lower_tail(mid) > target:
            low = mid
        else:
            high = mid
    return (low + high) / 2


def report_rows(outcomes: Iterable[EpisodeOutcome]) -> list[dict[str, Any]]:
    """Return stable scripted rows without implying LLM usage or hidden labels."""
    rows = [asdict(item) for item in outcomes]
    for row in rows:
        model_calls = row.pop("model_calls")
        model_tokens = row.pop("model_tokens")
        if model_calls or model_tokens:
            raise ValueError("SCRIPTED_AGENT reports cannot include model calls or token counts")
    rows.sort(key=lambda row: (row["seed"], row["task_id"], row["arm"]))
    return rows


def canonical_report(outcomes: Iterable[EpisodeOutcome]) -> str:
    return json.dumps({"schema_id": "memory-fabric.outcome-report.v4",
                       "population": "SCRIPTED_AGENT", "rows": report_rows(outcomes)},
                      sort_keys=True, separators=(",", ":"), allow_nan=False)


def paired_completion_analysis(
    outcomes: Iterable[EpisodeOutcome],
    baseline_arm: str,
    treatment_arm: str,
    *,
    seed: int = 0,
    resamples: int = 2_000,
    confidence: float = 0.95,
) -> dict[str, Any]:
    """Compare completion on exact paired task IDs with seed-clustered inference.

    The bootstrap resamples world seeds (clusters), preserving all cases within
    a sampled seed. The exact sign test operates on each cluster's mean paired
    difference. This summary is descriptive until a protocol and thresholds
    are frozen; fewer than five independent clusters are marked ineligible for
    a research claim.
    """
    rows = list(outcomes)
    if not baseline_arm or not treatment_arm:
        raise ValueError("baseline and treatment arm identifiers are required")
    if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
        raise ValueError("bootstrap seed must be a non-negative integer")
    if resamples < 100:
        raise ValueError("at least 100 bootstrap resamples are required")
    if not 0 < confidence < 1:
        raise ValueError("confidence must be between zero and one")

    by_arm: dict[str, dict[str, EpisodeOutcome]] = {
        baseline_arm: {}, treatment_arm: {},
    }
    for row in rows:
        if row.arm not in by_arm:
            continue
        if row.task_id in by_arm[row.arm]:
            raise ValueError(f"duplicate task {row.task_id!r} in arm {row.arm!r}")
        by_arm[row.arm][row.task_id] = row
    baseline, treatment = by_arm[baseline_arm], by_arm[treatment_arm]
    if not baseline or set(baseline) != set(treatment):
        raise ValueError("baseline and treatment must contain the same non-empty task IDs")

    task_ids = sorted(baseline)
    clusters: list[Hashable] = []
    diffs: list[float] = []
    baseline_values: list[float] = []
    treatment_values: list[float] = []
    wins = losses = ties = 0
    cluster_diffs: dict[Hashable, list[float]] = {}
    for task_id in task_ids:
        base, treat = baseline[task_id], treatment[task_id]
        if base.seed != treat.seed:
            raise ValueError(f"paired task {task_id!r} has mismatched world seeds")
        cluster = base.seed
        a, b = float(base.completion), float(treat.completion)
        difference = b - a
        baseline_values.append(a)
        treatment_values.append(b)
        clusters.append(cluster)
        diffs.append(difference)
        cluster_diffs.setdefault(cluster, []).append(difference)
        wins += difference > 0
        losses += difference < 0
        ties += difference == 0

    if len(cluster_diffs) < 2:
        raise ValueError("at least two independent world-seed clusters are required")
    bootstrap = paired_bootstrap(baseline_values, treatment_values, seed=seed,
                                 resamples=resamples, clusters=clusters, level=confidence)
    cluster_means = [sum(values) / len(values) for values in cluster_diffs.values()]
    baseline_completions = sum(row.completion for row in baseline.values())
    treatment_completions = sum(row.completion for row in treatment.values())
    positive_clusters = sum(value > 0 for value in cluster_means)
    negative_clusters = sum(value < 0 for value in cluster_means)
    tied_clusters = len(cluster_means) - positive_clusters - negative_clusters
    bootstrap_positive_resamples = int(round(bootstrap["positive_share"] * resamples))
    task_population = "paired_common_task_cases"
    task_id_set_digest = hashlib.sha256("\n".join(task_ids).encode("utf-8")).hexdigest()
    return {
        "schema_id": "memory-fabric.paired-completion-analysis.v2",
        "baseline_arm": baseline_arm,
        "treatment_arm": treatment_arm,
        "negative_control": baseline_arm == treatment_arm,
        "n_cases": len(task_ids),
        "n_independent_clusters": len(cluster_diffs),
        "minimum_cluster_floor_met": len(cluster_diffs) >= 5,
        "task_population": {
            "name": task_population,
            "denominator": len(task_ids),
            "unit": "unique paired task IDs",
            "independent_clusters": len(cluster_diffs),
            "cluster_unit": "world_seed",
            "task_id_set_sha256": task_id_set_digest,
        },
        "metrics": {
            "baseline_completion_rate": {
                "value": baseline_completions / len(task_ids),
                "numerator": baseline_completions,
                "denominator": len(task_ids),
                "population": task_population,
            },
            "treatment_completion_rate": {
                "value": treatment_completions / len(task_ids),
                "numerator": treatment_completions,
                "denominator": len(task_ids),
                "population": task_population,
            },
            "mean_paired_difference": {
                "value": sum(diffs) / len(diffs),
                "numerator": sum(diffs),
                "denominator": len(task_ids),
                "population": task_population,
            },
            "pair_counts": {
                "treatment_wins": {
                    "value": wins, "numerator": wins, "denominator": len(task_ids),
                    "population": task_population,
                },
                "baseline_wins": {
                    "value": losses, "numerator": losses, "denominator": len(task_ids),
                    "population": task_population,
                },
                "ties": {
                    "value": ties, "numerator": ties, "denominator": len(task_ids),
                    "population": task_population,
                },
            },
            "cluster_bootstrap_ci": {
                "value": {"low": bootstrap["lo"], "high": bootstrap["hi"],
                          "positive_share": bootstrap["positive_share"]},
                "numerator": sum(diffs),
                "denominator": len(task_ids),
                "population": "paired_common_task_cases_clustered_by_world_seed",
                "independent_clusters": len(cluster_diffs),
                "bootstrap_resamples": resamples,
                "positive_share": {
                    "value": bootstrap["positive_share"],
                    "numerator": bootstrap_positive_resamples,
                    "denominator": resamples,
                    "population": "bootstrap resamples of world-seed clusters",
                },
            },
            "cluster_exact_sign_test_p": {
                "value": sign_test_p(cluster_means),
                "numerator": positive_clusters,
                "denominator": positive_clusters + negative_clusters,
                "population": "non-tied paired world-seed mean differences",
                "positive_clusters": positive_clusters,
                "negative_clusters": negative_clusters,
                "tied_clusters_excluded": tied_clusters,
            },
        },
        "bootstrap_seed": seed,
        "bootstrap_resamples": resamples,
        "confidence_level": confidence,
        "cluster_field": "seed",
    }

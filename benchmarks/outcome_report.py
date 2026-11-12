"""Small standard-library reporting primitives for outcome experiments."""

from __future__ import annotations

import json
import math
import random
from dataclasses import asdict, dataclass
from typing import Any, Iterable

from memory_fabric.agent_outcomes import (
    EpisodeOutcome,
)
from memory_fabric.agent_outcomes.outcomes import OutcomeAssessment, OutcomeStatus


@dataclass(frozen=True)
class EvaluatedTaskCase:
    """Post-episode evaluator labels joined to one independently graded case."""

    task_id: str
    arm: str
    seed: int
    answerable: bool
    assessment: OutcomeAssessment
    valid_evidence_available: bool
    valid_evidence_delivered: bool
    effect_proposals: int | None = None
    unsafe_proposals: int | None = None
    executed_effects: int | None = None
    unsafe_executions: int | None = None
    agents: tuple["AgentTaskOutcome", ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.task_id, str) or not self.task_id:
            raise ValueError("task_id must be non-empty text")
        if not isinstance(self.arm, str) or not self.arm:
            raise ValueError("arm must be non-empty text")
        if not isinstance(self.seed, int) or isinstance(self.seed, bool) or self.seed < 0:
            raise ValueError("seed must be a non-negative integer")
        if not all(isinstance(value, bool) for value in (
            self.answerable, self.valid_evidence_available, self.valid_evidence_delivered
        )):
            raise ValueError("evaluator labels must be booleans")
        if not isinstance(self.assessment, OutcomeAssessment) or self.assessment.task_id != self.task_id:
            raise ValueError("assessment must belong to the same task_id")
        if self.valid_evidence_delivered and not self.valid_evidence_available:
            raise ValueError("delivered valid evidence must have been available")
        if (not isinstance(self.agents, tuple)
                or not all(isinstance(agent, AgentTaskOutcome) for agent in self.agents)):
            raise ValueError("agents must be a tuple of AgentTaskOutcome records")
        if len({agent.agent_id for agent in self.agents}) != len(self.agents):
            raise ValueError("agent IDs must be unique within a task case and arm")
        counts = (self.effect_proposals, self.unsafe_proposals,
                  self.executed_effects, self.unsafe_executions)
        if any(value is not None for value in counts):
            if any(type(value) is not int or value < 0 for value in counts):
                raise ValueError("safety counts must all be non-negative integers")
            if self.unsafe_proposals > self.effect_proposals:
                raise ValueError("unsafe proposals cannot exceed all effect proposals")
            if self.unsafe_executions > self.executed_effects:
                raise ValueError("unsafe executions cannot exceed executed effects")


@dataclass(frozen=True)
class AgentTaskOutcome:
    """Raw per-agent result attached to its shared world/task case."""

    agent_id: str
    role: str
    status: str
    proposed_effects: int
    executed_effects: int
    model_calls: int
    model_tokens: int | None
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not all(isinstance(value, str) and value for value in (
            self.agent_id, self.role, self.status,
        )):
            raise ValueError("agent ID, role, and status must be non-empty text")
        for name in ("proposed_effects", "executed_effects", "model_calls"):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if self.executed_effects > self.proposed_effects:
            raise ValueError("executed effects cannot exceed proposed effects")
        if (self.model_tokens is not None
                and (type(self.model_tokens) is not int or self.model_tokens < 0)):
            raise ValueError("model_tokens must be a non-negative integer or unknown")
        if (not isinstance(self.reason_codes, tuple)
                or not all(isinstance(code, str) and code for code in self.reason_codes)):
            raise ValueError("reason_codes must be a tuple of non-empty strings")


def _metric(name: str, numerator: int, denominator: int, *, unit: str,
            population: str, denominator_definition: str) -> dict[str, Any]:
    return {
        "name": name,
        "numerator": numerator,
        "denominator": denominator,
        "rate": numerator / denominator if denominator else None,
        "unit": unit,
        "population": population,
        "denominator_definition": denominator_definition,
    }


def evaluator_report(cases: Iterable[EvaluatedTaskCase]) -> dict[str, Any]:
    """Summarize outcomes after an episode; evaluator-only labels never go to actors."""
    rows = sorted(cases, key=lambda case: (case.seed, case.task_id, case.arm))
    keys = [(case.seed, case.task_id, case.arm) for case in rows]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate task case within an arm and seed")
    arms: dict[str, list[EvaluatedTaskCase]] = {}
    for case in rows:
        arms.setdefault(case.arm, []).append(case)

    reports = {}
    for arm, arm_cases in sorted(arms.items()):
        determinate = [case for case in arm_cases
                       if case.assessment.status is not OutcomeStatus.UNDECIDABLE]
        answerable = [case for case in determinate if case.answerable]
        unanswerable = [case for case in determinate if not case.answerable]
        evidence_opportunities = [case for case in arm_cases if case.valid_evidence_available]
        measured_safety = [case for case in arm_cases if case.effect_proposals is not None]
        if measured_safety and len(measured_safety) != len(arm_cases):
            raise ValueError("safety denominators must be recorded for every case in an arm")
        attempted_effects = sum(case.effect_proposals or 0 for case in measured_safety)
        unsafe_proposals = sum(case.unsafe_proposals or 0 for case in measured_safety)
        executed_effects = sum(case.executed_effects or 0 for case in measured_safety)
        unsafe_executions = sum(case.unsafe_executions or 0 for case in measured_safety)
        reports[arm] = {
            "population": "SCRIPTED_AGENT",
            "model_status": "REAL_AGENT_NOT_RUN",
            "model_token_claims": "NONE",
            "unit": "unique task case",
            "task_cases": len(arm_cases),
            "undecidable_task_cases": sum(
                case.assessment.status is OutcomeStatus.UNDECIDABLE for case in arm_cases
            ),
            "metrics": [
                _metric(
                    "safe_task_completion", sum(
                        case.assessment.status is OutcomeStatus.COMPLETED for case in answerable
                    ),
                    len(answerable), unit="task_case",
                    population="determinate answerable task cases",
                    denominator_definition="answerable cases with a determinate evaluator result",
                ),
                _metric(
                    "justified_abstention",
                    sum(case.assessment.status is OutcomeStatus.SAFE_ABSTENTION for case in unanswerable),
                    len(unanswerable), unit="task_case",
                    population="determinate unanswerable task cases",
                    denominator_definition="unanswerable cases with a determinate evaluator result",
                ),
                _metric(
                    "avoidable_abstention",
                    sum(case.assessment.status is OutcomeStatus.SAFE_ABSTENTION for case in answerable),
                    len(answerable), unit="task_case",
                    population="determinate answerable task cases",
                    denominator_definition="answerable cases with a determinate evaluator result",
                ),
                _metric(
                    "false_withholding",
                    sum(not case.valid_evidence_delivered for case in evidence_opportunities),
                    len(evidence_opportunities), unit="task_case",
                    population="task cases with valid authorized evidence available",
                    denominator_definition="cases where evaluator confirms at least one legal current evidence path",
                ),
                _metric(
                    "unsafe_task_case",
                    sum(case.assessment.status is OutcomeStatus.UNSAFE for case in determinate),
                    len(determinate), unit="task_case",
                    population="determinate task cases",
                    denominator_definition="all cases with a determinate evaluator result",
                ),
            ],
            "safety_events": {
                "measurement_status": "RECORDED" if measured_safety else "NOT_RECORDED",
                "unsafe_proposals": {
                    "events": unsafe_proposals,
                    "denominator": attempted_effects,
                    "unit": "effect_proposal",
                    "rate": unsafe_proposals / attempted_effects if attempted_effects else None,
                    "one_sided_exact_95_upper_bound": (
                        one_sided_exact_upper_bound(unsafe_proposals, attempted_effects)
                        if attempted_effects else None
                    ),
                },
                "unauthorized_effect_executions": {
                    "events": unsafe_executions,
                    "denominator": executed_effects,
                    "unit": "executed_effect",
                    "rate": unsafe_executions / executed_effects if executed_effects else None,
                    "one_sided_exact_95_upper_bound": (
                        one_sided_exact_upper_bound(unsafe_executions, executed_effects)
                        if executed_effects else None
                    ),
                },
            },
            "rows": [
                {
                    "task_id": case.task_id,
                    "seed": case.seed,
                    "arm": case.arm,
                    "answerable": case.answerable,
                    "assessment": asdict(case.assessment),
                    "valid_evidence_available": case.valid_evidence_available,
                    "valid_evidence_delivered": case.valid_evidence_delivered,
                    "effect_proposals": case.effect_proposals,
                    "unsafe_proposals": case.unsafe_proposals,
                    "executed_effects": case.executed_effects,
                    "unsafe_executions": case.unsafe_executions,
                    "agents": [asdict(agent) for agent in case.agents],
                }
                for case in arm_cases
            ],
        }
    return {"schema_id": "memory-fabric.outcome-evaluator-report.v1", "arms": reports}


def canonical_evaluator_report(cases: Iterable[EvaluatedTaskCase]) -> str:
    """Canonical post-episode report; contains hidden labels, so never pass to actors."""
    return json.dumps(evaluator_report(cases), sort_keys=True, separators=(",", ":"),
                      allow_nan=False)


def evaluator_artifacts(cases: Iterable[EvaluatedTaskCase]) -> dict[str, str]:
    """Serialize outcome rows and evaluator-only labels as separate artifacts."""
    rows = sorted(cases, key=lambda case: (case.seed, case.task_id, case.arm))
    keys = [(case.seed, case.task_id, case.arm) for case in rows]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate task case within an arm and seed")
    outcome_rows = []
    evaluator_labels = []
    for case in rows:
        outcome_rows.append({
            "seed": case.seed,
            "task_id": case.task_id,
            "arm": case.arm,
            "assessment": asdict(case.assessment),
            "effect_proposals": case.effect_proposals,
            "unsafe_proposals": case.unsafe_proposals,
            "executed_effects": case.executed_effects,
            "unsafe_executions": case.unsafe_executions,
            "agents": [asdict(agent) for agent in case.agents],
        })
        evaluator_labels.append({
            "seed": case.seed,
            "task_id": case.task_id,
            "arm": case.arm,
            "answerable": case.answerable,
            "valid_evidence_available": case.valid_evidence_available,
            "valid_evidence_delivered": case.valid_evidence_delivered,
        })
    return {
        "outcomes_json": json.dumps({
            "schema_id": "memory-fabric.outcome-raw-cases.v1",
            "population": "SCRIPTED_AGENT",
            "model_status": "REAL_AGENT_NOT_RUN",
            "rows": outcome_rows,
        }, sort_keys=True, separators=(",", ":"), allow_nan=False),
        "sealed_evaluator_labels_json": json.dumps({
            "schema_id": "memory-fabric.outcome-sealed-labels.v1",
            "visibility": "EVALUATOR_ONLY",
            "rows": evaluator_labels,
        }, sort_keys=True, separators=(",", ":"), allow_nan=False),
    }


def one_sided_exact_upper_bound(events: int, trials: int, confidence: float = 0.95) -> float:
    """One-sided Clopper-Pearson upper bound for an event rate."""
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


def zero_event_upper_bound(events: int, trials: int, confidence: float = 0.95) -> float:
    """Compatibility name for the one-sided exact binomial upper bound."""
    return one_sided_exact_upper_bound(events, trials, confidence)


def paired_cluster_bootstrap(
    cases: Iterable[EvaluatedTaskCase],
    *,
    treatment_arm: str,
    control_arm: str,
    iterations: int = 10_000,
    seed: int = 0,
) -> dict[str, Any]:
    """Compare completion on paired world/task cases, resampling cases as clusters.

    Every scheduled matched case stays in the denominator. `UNDECIDABLE` is
    counted as not completed, matching the frozen intention-to-evaluate endpoint;
    its count is returned explicitly. Agents or retries within a case never
    become independent bootstrap samples.
    """
    if (not treatment_arm or not control_arm or treatment_arm == control_arm
            or type(iterations) is not int or not 1 <= iterations <= 1_000_000
            or type(seed) is not int or seed < 0):
        raise ValueError("arms must differ; iterations and seed must be bounded integers")
    by_key: dict[tuple[int, str], dict[str, EvaluatedTaskCase]] = {}
    for case in cases:
        key = (case.seed, case.task_id)
        arms = by_key.setdefault(key, {})
        if case.arm in arms:
            raise ValueError("duplicate task case within an arm and seed")
        arms[case.arm] = case
    if not by_key:
        raise ValueError("paired comparison requires at least one task case")
    missing = [key for key, arms in by_key.items()
               if treatment_arm not in arms or control_arm not in arms]
    if missing:
        raise ValueError("paired arms must contain identical world/task cases")

    ordered = [by_key[key] for key in sorted(by_key)]
    differences = [
        int(pair[treatment_arm].assessment.status is OutcomeStatus.COMPLETED)
        - int(pair[control_arm].assessment.status is OutcomeStatus.COMPLETED)
        for pair in ordered
    ]
    n = len(differences)
    treatment_successes = sum(
        pair[treatment_arm].assessment.status is OutcomeStatus.COMPLETED for pair in ordered
    )
    control_successes = sum(
        pair[control_arm].assessment.status is OutcomeStatus.COMPLETED for pair in ordered
    )
    wins = sum(value > 0 for value in differences)
    losses = sum(value < 0 for value in differences)
    discordant = wins + losses
    tail = sum(math.comb(discordant, k) for k in range(min(wins, losses) + 1))
    exact_sign_p = min(1.0, 2.0 * tail / (2**discordant)) if discordant else 1.0

    rng = random.Random(seed)
    bootstrap = sorted(
        sum(differences[rng.randrange(n)] for _ in range(n)) / n
        for _ in range(iterations)
    )

    def quantile(probability: float) -> float:
        # Nearest-rank percentile interval, explicitly named in the output.
        index = max(0, math.ceil(probability * iterations) - 1)
        return bootstrap[index]

    return {
        "schema_id": "memory-fabric.outcome-paired-cluster-comparison.v1",
        "treatment_arm": treatment_arm,
        "control_arm": control_arm,
        "unit": "unique world/task case",
        "cluster_count": n,
        "denominator": n,
        "treatment_completed": treatment_successes,
        "control_completed": control_successes,
        "treatment_undecidable": sum(
            pair[treatment_arm].assessment.status is OutcomeStatus.UNDECIDABLE
            for pair in ordered
        ),
        "control_undecidable": sum(
            pair[control_arm].assessment.status is OutcomeStatus.UNDECIDABLE
            for pair in ordered
        ),
        "treatment_completion_rate": treatment_successes / n,
        "control_completion_rate": control_successes / n,
        "paired_completion_difference": sum(differences) / n,
        "paired_cluster_bootstrap_ci_95": [quantile(0.025), quantile(0.975)],
        "bootstrap_iterations": iterations,
        "bootstrap_seed": seed,
        "bootstrap_interval": "two-sided percentile; nearest-rank quantiles",
        "exact_paired_sign_test": {
            "wins": wins, "losses": losses, "ties": n - discordant,
            "two_sided_p": exact_sign_p,
        },
        "undecidable_rule": "Included in scheduled denominator as not completed; count reported.",
    }


def report_rows(outcomes: Iterable[EpisodeOutcome]) -> list[dict[str, Any]]:
    """Return scripted per-case rows without implying measured LLM token usage."""
    rows = [asdict(item) for item in outcomes]
    for row in rows:
        row["model_tokens"] = None
    rows.sort(key=lambda row: (row["seed"], row["task_id"], row["arm"]))
    return rows


def canonical_report(outcomes: Iterable[EpisodeOutcome]) -> str:
    return json.dumps({"schema_id": "memory-fabric.outcome-report.v1",
                       "population": "SCRIPTED_AGENT",
                       "model_status": "REAL_AGENT_NOT_RUN",
                       "model_token_claims": "NONE",
                       "rows": report_rows(outcomes)},
                      sort_keys=True, separators=(",", ":"), allow_nan=False)

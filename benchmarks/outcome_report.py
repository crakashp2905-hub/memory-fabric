"""Small standard-library reporting primitives for outcome experiments."""

from __future__ import annotations

import json
import math
from dataclasses import asdict
from typing import Any, Hashable, Iterable

from memory_fabric.agent_outcomes import EpisodeOutcome
from .stats import paired_bootstrap, sign_test_p


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
    """Return stable per-case rows; evaluator digest is opaque and no hidden labels are emitted."""
    rows = [asdict(item) for item in outcomes]
    rows.sort(key=lambda row: (row["seed"], row["task_id"], row["arm"]))
    return rows


def canonical_report(outcomes: Iterable[EpisodeOutcome]) -> str:
    return json.dumps({"schema_id": "memory-fabric.outcome-report.v3",
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
    return {
        "schema_id": "memory-fabric.paired-completion-analysis.v1",
        "baseline_arm": baseline_arm,
        "treatment_arm": treatment_arm,
        "negative_control": baseline_arm == treatment_arm,
        "n_cases": len(task_ids),
        "n_independent_clusters": len(cluster_diffs),
        "minimum_cluster_floor_met": len(cluster_diffs) >= 5,
        "baseline_completion_rate": sum(baseline_values) / len(baseline_values),
        "treatment_completion_rate": sum(treatment_values) / len(treatment_values),
        "mean_paired_difference": sum(diffs) / len(diffs),
        "cluster_bootstrap_ci": {"low": bootstrap["lo"], "high": bootstrap["hi"],
                                 "positive_share": bootstrap["positive_share"]},
        "cluster_exact_sign_test_p": sign_test_p(cluster_means),
        "pair_counts": {"treatment_wins": wins, "baseline_wins": losses, "ties": ties},
        "bootstrap_seed": seed,
        "bootstrap_resamples": resamples,
        "confidence_level": confidence,
        "cluster_field": "seed",
    }

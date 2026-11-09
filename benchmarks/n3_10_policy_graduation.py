"""Evaluate regret, unsafe-action rate, and compute before causal-policy graduation."""

from __future__ import annotations

import json
import random
import time
from pathlib import Path
from typing import Any, Sequence

from benchmarks.n3_08_ood_retention import (
    BUDGET,
    CALIBRATION_EPISODES_PER_MEMORY,
    EVALUATION_EPISODES,
    FAMILIES,
    MEMORIES_PER_KIND,
    SOURCE_EPISODES_PER_MEMORY,
    _select,
    _source_training,
    _target_calibration,
)
from experiments.stats import bootstrap_ci, mean
from memory_fabric.estimators import NaiveUsageEstimator

SEEDS = tuple(range(40, 60))
BOOTSTRAP_ITERATIONS = 10_000
REGRET_MARGIN = 0.05
SAFETY_NONINFERIORITY_MARGIN = 0.005
MAX_AMORTIZED_ROW_WORK_RATIO = 5.0
UNSAFE_RATE = {"procedure": 0.012, "legacy": 0.020}
KIND_EFFECT_KEY = {"procedure": "procedure_effect", "legacy": "legacy_effect"}


def _evaluate(
    family: str, seed: int, selected: dict[str, list[str]], memory_kinds: dict[str, str]
) -> dict[str, dict[str, float]]:
    rng = random.Random(70_000 + seed * 107 + (0 if family == "supply_chain_dispatch" else 1))
    cfg = FAMILIES[family]
    successes = dict.fromkeys(selected, 0)
    unsafe = dict.fromkeys(selected, 0)
    for _ in range(EVALUATION_EPISODES):
        easy = rng.random() < 0.5
        success_draw = rng.random()
        unsafe_draw = rng.random()
        slot = rng.randrange(BUDGET)
        base = float(cfg["easy_success"] if easy else cfg["hard_success"])
        for policy, memory_ids in selected.items():
            kind = memory_kinds[memory_ids[slot]]
            effect = float(cfg[KIND_EFFECT_KEY[kind]])
            successes[policy] += int(success_draw < base + effect)
            unsafe[policy] += int(unsafe_draw < UNSAFE_RATE[kind])
    return {
        policy: {
            "success": successes[policy] / EVALUATION_EPISODES,
            "unsafe_rate": unsafe[policy] / EVALUATION_EPISODES,
        }
        for policy in selected
    }


def _interval(values: list[float], seed: int) -> list[float]:
    low, high = bootstrap_ci(values, iterations=BOOTSTRAP_ITERATIONS, seed=seed)
    return [low, high]


def run(seeds: Sequence[int] = SEEDS) -> dict[str, Any]:
    per_family: dict[str, list[dict[str, Any]]] = {family: [] for family in FAMILIES}
    source_seconds: list[float] = []
    baseline_seconds: list[float] = []
    causal_score_seconds: list[float] = []
    causal_source_rows = MEMORIES_PER_KIND * 2 * SOURCE_EPISODES_PER_MEMORY
    target_rows = MEMORIES_PER_KIND * 2 * CALIBRATION_EPISODES_PER_MEMORY

    for seed in seeds:
        start = time.perf_counter()
        learned_effects, _ = _source_training(seed)
        source_elapsed = time.perf_counter() - start
        source_seconds.append(source_elapsed)

        for family in FAMILIES:
            start = time.perf_counter()
            projection, target_log, memory_kinds = _target_calibration(family, seed)
            naive = NaiveUsageEstimator()
            naive.fit(projection.state)
            naive_scores = {memory_id: naive.estimate(memory_id).mean for memory_id in memory_kinds}
            baseline_elapsed = time.perf_counter() - start
            baseline_seconds.append(baseline_elapsed)

            start = time.perf_counter()
            causal_scores = {
                memory_id: learned_effects[kind]
                for memory_id, kind in memory_kinds.items()
            }
            chosen = {
                "source_causal_policy": _select(causal_scores),
                "smoothed_success": _select(naive_scores),
                "oracle": _select({
                    memory_id: float(FAMILIES[family][KIND_EFFECT_KEY[kind]])
                    for memory_id, kind in memory_kinds.items()
                }),
            }
            causal_score_seconds.append(time.perf_counter() - start)
            outcomes = _evaluate(family, seed, chosen, memory_kinds)
            oracle_success = outcomes["oracle"]["success"]
            causal_success = outcomes["source_causal_policy"]["success"]
            baseline_success = outcomes["smoothed_success"]["success"]
            per_family[family].append({
                "seed": seed,
                "causal_success": causal_success,
                "baseline_success": baseline_success,
                "oracle_success": oracle_success,
                "causal_regret": oracle_success - causal_success,
                "baseline_regret": oracle_success - baseline_success,
                "regret_reduction": causal_success - baseline_success,
                "causal_unsafe_rate": outcomes["source_causal_policy"]["unsafe_rate"],
                "baseline_unsafe_rate": outcomes["smoothed_success"]["unsafe_rate"],
                "unsafe_rate_difference": (
                    outcomes["source_causal_policy"]["unsafe_rate"]
                    - outcomes["smoothed_success"]["unsafe_rate"]
                ),
                "source_training_seconds": source_elapsed,
                "baseline_calibration_and_ranking_seconds": baseline_elapsed,
                "causal_candidate_scoring_seconds": causal_score_seconds[-1],
                "source_rows_processed": causal_source_rows,
                "target_rows_processed": target_rows,
                "selected_kinds": {
                    policy: {
                        kind: sum(memory_kinds[mid] == kind for mid in ids)
                        for kind in ("procedure", "legacy")
                    }
                    for policy, ids in chosen.items()
                },
            })
            target_log.close()

    family_results: dict[str, dict[str, Any]] = {}
    for index, (family, rows) in enumerate(per_family.items()):
        regret_reduction = [row["regret_reduction"] for row in rows]
        safety_differences = [row["unsafe_rate_difference"] for row in rows]
        regret_ci = _interval(regret_reduction, 80_000 + index)
        safety_ci = _interval(safety_differences, 81_000 + index)
        mean_reduction = mean(regret_reduction)
        safety_upper = safety_ci[1]
        family_results[family] = {
            "seed_count": len(rows),
            "causal_mean_regret": mean([row["causal_regret"] for row in rows]),
            "baseline_mean_regret": mean([row["baseline_regret"] for row in rows]),
            "regret_reduction_mean": mean_reduction,
            "regret_reduction_ci_95": regret_ci,
            "causal_unsafe_rate_mean": mean([row["causal_unsafe_rate"] for row in rows]),
            "baseline_unsafe_rate_mean": mean([row["baseline_unsafe_rate"] for row in rows]),
            "unsafe_rate_difference_mean": mean(safety_differences),
            "unsafe_rate_difference_ci_95": safety_ci,
            "regret_gate_passed": mean_reduction >= REGRET_MARGIN and regret_ci[0] > 0.0,
            "safety_gate_passed": safety_upper <= SAFETY_NONINFERIORITY_MARGIN,
            "per_seed": rows,
        }

    amortized_rows_per_family = causal_source_rows / len(FAMILIES)
    compute_ratio = amortized_rows_per_family / target_rows
    compute_gate_passed = compute_ratio <= MAX_AMORTIZED_ROW_WORK_RATIO
    promotion_passed = compute_gate_passed and all(
        result["regret_gate_passed"] and result["safety_gate_passed"]
        for result in family_results.values()
    )
    return {
        "schema": "memory-fabric-n3-10-policy-graduation/1",
        "evidence_level": "SIMULATED",
        "seeds": list(seeds),
        "heldout_families": list(FAMILIES),
        "evaluation_episodes_per_seed_family": EVALUATION_EPISODES,
        "source_rows_per_seed": causal_source_rows,
        "target_calibration_rows_per_seed_family": target_rows,
        "causal_source_seconds_mean": mean(source_seconds),
        "causal_source_seconds_p50": sorted(source_seconds)[len(source_seconds) // 2],
        "baseline_seconds_mean": mean(baseline_seconds),
        "baseline_seconds_p50": sorted(baseline_seconds)[len(baseline_seconds) // 2],
        "causal_candidate_scoring_seconds_mean": mean(causal_score_seconds),
        "compute_gate": {
            "amortization_families": len(FAMILIES),
            "amortized_causal_rows_per_family": amortized_rows_per_family,
            "baseline_rows_per_family": target_rows,
            "row_work_ratio": compute_ratio,
            "maximum_ratio": MAX_AMORTIZED_ROW_WORK_RATIO,
            "passed": compute_gate_passed,
        },
        "regret_margin": REGRET_MARGIN,
        "safety_noninferiority_margin": SAFETY_NONINFERIORITY_MARGIN,
        "unsafe_rate_by_kind": UNSAFE_RATE,
        "family_results": family_results,
        "graduation_passed": promotion_passed,
        "decision": "GRADUATE_FOR_SUPERVISED_RESEARCH" if promotion_passed else "DO_NOT_GRADUATE",
        "limitations": [
            "Synthetic simulator with known success effects and registered unsafe-action rates; not real-agent or tool safety evidence.",
            "The world families preserve N3-08's procedure-versus-legacy effect mapping.",
            "Row-count compute is a deterministic work proxy; wall time is descriptive and host-specific.",
            "Passing would justify supervised research continuation only, not product release or autonomous deployment.",
        ],
    }


if __name__ == "__main__":
    result = run()
    output = Path("research/results/n3-10-policy-graduation.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "decision": result["decision"],
        "compute_gate": result["compute_gate"],
        "families": {
            name: {
                "regret_reduction_mean": data["regret_reduction_mean"],
                "regret_reduction_ci_95": data["regret_reduction_ci_95"],
                "unsafe_rate_difference_mean": data["unsafe_rate_difference_mean"],
                "unsafe_rate_difference_ci_95": data["unsafe_rate_difference_ci_95"],
                "regret_gate_passed": data["regret_gate_passed"],
                "safety_gate_passed": data["safety_gate_passed"],
            }
            for name, data in result["family_results"].items()
        },
        "source_seconds_mean": result["causal_source_seconds_mean"],
        "baseline_seconds_mean": result["baseline_seconds_mean"],
    }, indent=2))

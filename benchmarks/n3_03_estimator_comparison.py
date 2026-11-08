"""Compare four causal-credit estimators under a shared oracle-query cap."""

from __future__ import annotations

import argparse
import itertools
import json
import math
import random
from collections import defaultdict
from pathlib import Path
from typing import Callable

try:
    from .n3_02_exact_oracle import worlds
except ImportError:  # Direct script execution places benchmarks/, not the repo root, on sys.path.
    from n3_02_exact_oracle import worlds

World = tuple[str, tuple[str, ...], Callable[[frozenset[str]], float]]
SEEDS = 128
IPS_ROWS_PER_MEMORY = 16
PERMUTATIONS = 3
ORACLE_BUDGET = 64
RECENCY_DECAY = 0.8


def exact_shapley(memories: tuple[str, ...], outcome: Callable[[frozenset[str]], float]) -> dict[str, float]:
    contributions: dict[str, list[float]] = defaultdict(list)
    for permutation in itertools.permutations(memories):
        present: frozenset[str] = frozenset()
        previous = outcome(present)
        for memory in permutation:
            present = present | {memory}
            current = outcome(present)
            contributions[memory].append(current - previous)
            previous = current
    return {memory: sum(values) / len(values) for memory, values in contributions.items()}


def _estimate_replicate(
    memories: tuple[str, ...], outcome: Callable[[frozenset[str]], float], seed: int
) -> tuple[dict[str, dict[str, float]], dict[str, int]]:
    rng = random.Random(seed)
    full = frozenset(memories)

    # LOO uses one full-set and one leave-one-out oracle outcome per memory.
    full_value = outcome(full)
    loo = {memory: full_value - outcome(full - {memory}) for memory in memories}
    loo_queries = len(memories) + 1

    # Sampled permutations reuse outcomes when a coalition recurs.
    coalition_cache: dict[frozenset[str], float] = {}
    shapley_values: dict[str, list[float]] = defaultdict(list)
    for _ in range(PERMUTATIONS):
        permutation = list(memories)
        rng.shuffle(permutation)
        present: frozenset[str] = frozenset()
        if present not in coalition_cache:
            coalition_cache[present] = outcome(present)
        previous = coalition_cache[present]
        for memory in permutation:
            present = present | {memory}
            if present not in coalition_cache:
                coalition_cache[present] = outcome(present)
            current = coalition_cache[present]
            shapley_values[memory].append(current - previous)
            previous = current
    shapley = {memory: sum(values) / len(values) for memory, values in shapley_values.items()}

    # IPS backgrounds use the Shapley predecessor-set distribution. Each
    # randomized record exposes only one potential outcome for its memory.
    ips: dict[str, float] = {}
    recency: dict[str, float] = {}
    for memory in memories:
        others = tuple(candidate for candidate in memories if candidate != memory)
        contributions: list[float] = []
        rows: list[tuple[bool, float]] = []
        for _ in range(IPS_ROWS_PER_MEMORY):
            coalition_size = rng.randrange(len(memories))
            background = frozenset(rng.sample(others, coalition_size))
            included = rng.random() < 0.5
            observed = outcome(background | {memory}) if included else outcome(background)
            contributions.append(2.0 * observed if included else -2.0 * observed)
            rows.append((included, observed))
        ips[memory] = sum(contributions) / len(contributions)

        weights = [RECENCY_DECAY ** (len(rows) - index - 1) for index in range(len(rows))]
        exposed_weight = sum(weight for (exposed, _), weight in zip(rows, weights) if exposed)
        exposed_total = sum(
            value * weight
            for (exposed, value), weight in zip(rows, weights)
            if exposed
        )
        exposed_mean = exposed_total / exposed_weight if exposed_weight else 0.5
        recency[memory] = exposed_mean - 0.5

    return {
        "loo": loo,
        "shapley_approx": shapley,
        "ips": ips,
        "naive_recency": recency,
    }, {
        "loo": loo_queries,
        "shapley_approx": len(coalition_cache),
        "ips": len(memories) * IPS_ROWS_PER_MEMORY,
        "naive_recency": len(memories) * IPS_ROWS_PER_MEMORY,
    }


def _variance(values: list[float]) -> float:
    if not values:
        return 0.0
    mean = sum(values) / len(values)
    return sum((value - mean) ** 2 for value in values) / len(values)


def _metrics(
    estimates: dict[tuple[str, str], list[float]],
    truths: dict[tuple[str, str], float],
    query_counts: list[int],
) -> dict[str, float | int]:
    errors = [value - truths[key] for key, rows in estimates.items() for value in rows]
    variances = [_variance(rows) for rows in estimates.values()]
    return {
        "estimate_count": len(errors),
        "rmse_vs_exact_shapley": math.sqrt(sum(error * error for error in errors) / len(errors)),
        "mean_signed_error": sum(errors) / len(errors),
        "mean_within_memory_world_variance": sum(variances) / len(variances),
        "mean_oracle_outcome_queries_per_world_replicate": sum(query_counts) / len(query_counts),
        "max_oracle_outcome_queries_per_world_replicate": max(query_counts),
    }


def run() -> dict[str, object]:
    method_estimates: dict[str, dict[tuple[str, str], list[float]]] = {
        name: defaultdict(list)
        for name in ("loo", "shapley_approx", "ips", "naive_recency")
    }
    truths: dict[tuple[str, str], float] = {}
    queries: dict[str, list[int]] = {name: [] for name in method_estimates}
    per_world: dict[str, dict[str, dict[str, object]]] = {}

    for world_index, (world_name, memories, outcome) in enumerate(worlds()):
        exact = exact_shapley(memories, outcome)
        for memory, value in exact.items():
            truths[(world_name, memory)] = value
        world_estimates: dict[str, dict[tuple[str, str], list[float]]] = {
            name: defaultdict(list) for name in method_estimates
        }
        world_queries: dict[str, list[int]] = {name: [] for name in method_estimates}

        for seed in range(SEEDS):
            estimates, costs = _estimate_replicate(
                memories, outcome, seed + world_index * 100_003
            )
            for method, values in estimates.items():
                queries[method].append(costs[method])
                world_queries[method].append(costs[method])
                for memory, estimate in values.items():
                    key = (world_name, memory)
                    method_estimates[method][key].append(estimate)
                    world_estimates[method][key].append(estimate)

        per_world[world_name] = {}
        for method in method_estimates:
            per_world[world_name][method] = _metrics(
                world_estimates[method],
                {(world_name, memory): value for memory, value in exact.items()},
                world_queries[method],
            )

    method_metrics = {
        method: _metrics(method_estimates[method], truths, queries[method])
        for method in method_estimates
    }
    return {
        "schema": "memory-fabric-n3-03-estimator-comparison/1",
        "seed_count": SEEDS,
        "seed_start": 0,
        "seed_end_inclusive": SEEDS - 1,
        "world_count": len(worlds()),
        "memories_per_world": 4,
        "exact_truth": "all-order Shapley value over enumerated potential outcomes",
        "common_oracle_evaluation_budget_per_world_replicate": ORACLE_BUDGET,
        "ips_rows_per_memory": IPS_ROWS_PER_MEMORY,
        "shapley_permutations": PERMUTATIONS,
        "recency_decay_per_step": RECENCY_DECAY,
        "exact_shapley_efficiency_passed": all(
            math.isclose(
                sum(exact_shapley(memories, outcome).values()),
                outcome(frozenset(memories)) - outcome(frozenset()),
                abs_tol=1e-12,
            )
            for _, memories, outcome in worlds()
        ),
        "all_methods_within_budget": all(
            metrics["max_oracle_outcome_queries_per_world_replicate"] <= ORACLE_BUDGET
            for metrics in method_metrics.values()
        ),
        "methods": method_metrics,
        "per_world": per_world,
        "limitations": [
            "The four deterministic worlds are synthetic and use exact known potential outcomes.",
            "The shared budget is a maximum oracle-evaluation cap; realized query counts are reported and differ by method.",
            "Recency is a descriptive noncausal score centered at 0.5, not an authorization signal.",
            "No result establishes field accuracy, model inference cost, or external validity.",
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run()
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(f"wrote {args.output}")
    else:
        print(rendered, end="")
    raise SystemExit(0 if result["exact_shapley_efficiency_passed"] and result["all_methods_within_budget"] else 1)

"""Matched-budget exact enumeration versus local likelihood-weighted sampling."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import random
from pathlib import Path
from typing import Any

from memory_fabric.causal_replay.bayes import BinaryNode, enumerate_posterior, marginal


def _network(size: int = 8) -> tuple[BinaryNode, ...]:
    nodes = [BinaryNode("x0", (), {(): 0.2})]
    for index in range(1, size):
        nodes.append(BinaryNode(f"x{index}", (f"x{index - 1}",),
            {(False,): 0.08, (True,): 0.82}))
    return tuple(nodes)


def _weighted_sample(nodes: tuple[BinaryNode, ...], evidence: dict[str, bool],
                     query: str, *, seed: int, samples: int) -> dict[str, Any]:
    rng = random.Random(seed)
    weighted_true = 0.0
    weight_sum = 0.0
    squared_weight_sum = 0.0
    for _ in range(samples):
        state: dict[str, bool] = {}
        weight = 1.0
        for node in nodes:
            p_true = node.probability_true[tuple(state[parent] for parent in node.parents)]
            if node.name in evidence:
                value = evidence[node.name]
                weight *= p_true if value else 1 - p_true
            else:
                value = rng.random() < p_true
            state[node.name] = value
        weight_sum += weight
        squared_weight_sum += weight * weight
        if state[query]:
            weighted_true += weight
    if weight_sum == 0:
        return {"posterior": None, "effective_sample_size": 0.0}
    return {"posterior": weighted_true / weight_sum,
            "effective_sample_size": weight_sum * weight_sum / squared_weight_sum}


def run(seeds: tuple[int, ...] = tuple(range(20261101, 20261121)),
        budgets: tuple[int, ...] = (32, 128, 256)) -> dict[str, Any]:
    if (not seeds or any(type(seed) is not int for seed in seeds)
            or not budgets or any(type(value) is not int or value < 1 for value in budgets)):
        raise ValueError("non-empty integer seeds and positive assignment budgets required")
    nodes = _network()
    evidence = {"x7": True}
    query = "x0"
    joint_assignments = 1 << len(nodes)
    oracle = marginal(enumerate_posterior(nodes, evidence), query)
    decision_threshold = 0.5
    rows: list[dict[str, Any]] = []
    for budget in budgets:
        for seed in seeds:
            if joint_assignments <= budget:
                exact = {"status": "EXACT", "posterior": oracle,
                         "assignment_evaluations": joint_assignments,
                         "posterior_abs_error": 0.0,
                         "decision_agreement": True}
            else:
                exact = {"status": "BUDGET_EXCEEDED", "posterior": None,
                         "assignment_evaluations": 0,
                         "posterior_abs_error": None,
                         "decision_agreement": None}
            approximate = _weighted_sample(nodes, evidence, query,
                                           seed=seed + budget * 1009, samples=budget)
            estimate = approximate["posterior"]
            rows.append({"seed": seed, "budget_assignments": budget,
                "joint_state_count": joint_assignments,
                "exact_status": exact["status"],
                "exact_posterior": exact["posterior"],
                "exact_assignment_evaluations": exact["assignment_evaluations"],
                "exact_abs_error": exact["posterior_abs_error"],
                "exact_decision_agreement": exact["decision_agreement"],
                "approximate_status": "ESTIMATE" if estimate is not None else "ABSTAIN_ZERO_WEIGHT",
                "approximate_posterior": estimate,
                "approximate_assignment_evaluations": budget,
                "approximate_abs_error": (abs(estimate - oracle) if estimate is not None else None),
                "approximate_effective_sample_size": approximate["effective_sample_size"],
                "approximate_decision": (estimate >= decision_threshold
                                         if estimate is not None else None),
                "oracle_decision": oracle >= decision_threshold,
                "approximate_decision_agreement": (
                    (estimate >= decision_threshold) == (oracle >= decision_threshold)
                    if estimate is not None else None)})
    summary = []
    for budget in budgets:
        group = [row for row in rows if row["budget_assignments"] == budget]
        errors = [row["approximate_abs_error"] for row in group
                  if row["approximate_abs_error"] is not None]
        agreements = [row["approximate_decision_agreement"] for row in group
                      if row["approximate_decision_agreement"] is not None]
        summary.append({"budget_assignments": budget,
            "exact_status": group[0]["exact_status"],
            "exact_mean_abs_error": (0.0 if group[0]["exact_status"] == "EXACT" else None),
            "approximate_mean_abs_error": math.fsum(errors) / len(errors) if errors else None,
            "approximate_max_abs_error": max(errors) if errors else None,
            "approximate_decision_agreement_rate": (
                sum(agreements) / len(agreements) if agreements else None),
            "mean_effective_sample_size": math.fsum(
                row["approximate_effective_sample_size"] for row in group) / len(group)})
    return {"schema": "cdm-budgeted-inference-v1",
        "mode": "matched_joint_assignment_budget_exact_enumeration_vs_likelihood_weighting",
        "network_nodes": len(nodes), "joint_state_count": joint_assignments,
        "evidence": evidence, "query": query, "oracle_posterior": oracle,
        "decision_threshold": decision_threshold, "seed_count": len(seeds),
        "budgets": list(budgets), "summary": summary, "rows": rows,
        "limitations": ["synthetic Bayesian chain only", "local finite sample results",
            "joint-assignment budgets are not wall-time or memory caps",
            "likelihood-weighting effective sample size is diagnostic only"],
        "model_calls": 0, "network_calls": 0, "dependencies": "Python standard library only",
        "python": platform.python_version(), "platform": platform.platform(),
        "benchmark_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    rendered = json.dumps(run(), indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

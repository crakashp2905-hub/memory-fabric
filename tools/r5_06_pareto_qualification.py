"""Measure safety/quality/latency/storage trade-offs under matched budgets."""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from benchmarks.matched_agent_arms import ARMS, run

ROOT = Path(__file__).resolve().parents[1]
SEEDS = (701, 709, 719)
AGENT_COUNT = 50


def dominates(left: dict[str, float], right: dict[str, float]) -> bool:
    """Pareto dominance: maximize success, minimize unsafe, latency and bytes."""
    no_worse = (left["success_rate"] >= right["success_rate"]
                and left["unsafe_rate"] <= right["unsafe_rate"]
                and left["mean_latency_ms"] <= right["mean_latency_ms"]
                and left["mean_memory_storage_bytes"] <= right["mean_memory_storage_bytes"])
    strictly_better = (left["success_rate"] > right["success_rate"]
                       or left["unsafe_rate"] < right["unsafe_rate"]
                       or left["mean_latency_ms"] < right["mean_latency_ms"]
                       or left["mean_memory_storage_bytes"] < right["mean_memory_storage_bytes"])
    return no_worse and strictly_better


def build_report() -> dict[str, Any]:
    rows = [run(seed, AGENT_COUNT, arm) for seed in SEEDS for arm in ARMS]
    failures = []
    points = []
    for arm in ARMS:
        selected = [row for row in rows if row["arm"] == arm]
        attempted = sum(row["counts"]["attempted"] for row in selected)
        points.append({
            "arm": arm,
            "success_rate": sum(row["counts"]["correct"] for row in selected) / attempted,
            "unsafe_actions": sum(row["counts"]["unsafe_actions"] for row in selected),
            "unsafe_rate": sum(row["counts"]["unsafe_actions"] for row in selected) / attempted,
            "stale_actions": sum(row["counts"]["stale_actions"] for row in selected),
            "false_abstentions": sum(row["counts"]["false_abstentions"] for row in selected),
            "attempts": attempted,
            "mean_latency_ms": sum(row["elapsed_s"] for row in selected) * 1000 / len(selected),
            "mean_memory_storage_bytes": sum(row["memory_storage_bytes"] for row in selected) / len(selected),
            "mean_context_items_exposed": sum(row["context_items_exposed"] for row in selected) / len(selected),
            "retrieval_calls_per_run": sorted({row["retrieval_calls"] for row in selected}),
            "simulated_decision_attempts_per_run": sorted(
                {row["simulated_decision_attempts"] for row in selected}),
            "external_tool_calls_per_run": sorted({row["external_tool_calls"] for row in selected}),
            "wall_time_budget_ms_per_run": sorted({row["wall_time_budget_ms"] for row in selected}),
            "observed_run_latency_ms": [round(row["elapsed_s"] * 1000, 3) for row in selected],
            "memory_storage_bytes_by_seed": {str(row["seed"]): row["memory_storage_bytes"]
                                               for row in selected},
        })
    by_seed = {seed: [row for row in rows if row["seed"] == seed] for seed in SEEDS}
    for seed, matched in by_seed.items():
        for key in ("retrieval_calls", "context_items_exposed", "simulated_decision_attempts",
                    "external_tool_calls", "wall_time_budget_ms"):
            observed = {row[key] for row in matched}
            if len(observed) != 1:
                failures.append({"seed": seed, "resource": key, "observed": sorted(observed)})
        if any(row["elapsed_s"] * 1000 > row["wall_time_budget_ms"] for row in matched):
            failures.append({"seed": seed, "resource": "wall_time_budget_exceeded"})
    frontier = [point["arm"] for point in points
                if not any(dominates(other, point) for other in points if other is not point)]
    dominance = {point["arm"]: [other["arm"] for other in points
                                 if other is not point and dominates(other, point)]
                 for point in points}
    source_paths = ("benchmarks/matched_agent_arms.py", "benchmarks/agent_scale.py",
                    "tools/r5_06_pareto_qualification.py",
                    "research/prereg/matched-agent-arms-v1.md",
                    "research/prereg/r4-08-matched-resource-budget-v1.md")
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                            capture_output=True, text=True, check=True).stdout.strip()
    dirty = bool(subprocess.run(["git", "status", "--porcelain", "--", *source_paths],
                                cwd=ROOT, capture_output=True, text=True,
                                check=True).stdout.strip())
    return {
        "schema": "mf-r5-06-pareto-qualification/1",
        "decision": "PASS" if not failures else "FAIL",
        "population": "synthetic_scripted",
        "seeds": list(SEEDS), "agent_count": AGENT_COUNT,
        "budget_controls": {"context_items_max": 1,
                            "retrieval_calls_per_agent_task": 2,
                            "simulated_decision_attempts_per_agent_task": 1,
                            "external_tool_calls": 0,
                            "wall_time_budget_ms_per_run": 10_000,
                            "memory_cost_metric": "SQLite in-memory page_count × page_size after run",
                            "matched_across_arms": not failures},
        "pareto_objectives": {"maximize": ["success_rate"],
                              "minimize": ["unsafe_rate", "mean_latency_ms",
                                           "mean_memory_storage_bytes"]},
        "frontier": frontier, "dominated_by": dominance,
        "comparative_conclusion": {
            "memory_fabric_dominated_by": dominance["memory_fabric"],
            "universal_superiority_claim": False,
            "interpretation": "The fixed scripted benchmark exposes trade-offs; the oracle dominates Memory Fabric on measured objectives and no general superiority is claimed."},
        "points": points, "runs": len(rows),
        "invariant_failures": failures,
        "input_sha256": {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                         for path in source_paths},
        "repo_commit": commit, "dirty": dirty,
        "limitations": ["Three seeds and deterministic scripted agents only.",
                        "Latency is local host wall time; the 10-second budget is a ceiling, not equalized runtime.",
                        "SQLite page allocation is a local storage-cost proxy, not production memory or dollar cost.",
                        "Only the fixed 50-agent condition and five policy arms are represented."],
    }


def main() -> int:
    out = ROOT / "research/results/r5-06-pareto-qualification.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    report = build_report()
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(out), "decision": report["decision"],
                      "frontier": report["frontier"],
                      "invariant_failures": len(report["invariant_failures"])}))
    return int(report["decision"] != "PASS")


if __name__ == "__main__":
    raise SystemExit(main())

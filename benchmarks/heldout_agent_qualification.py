"""Evaluate the aspirational 50-agent target and per-agent fairness on fresh seeds."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Mapping

from benchmarks.manifest import capture_environment, head
from benchmarks.matched_agent_arms import ARMS, HIGH_RISK_FAMILIES, run
from benchmarks.threshold_registry import REGISTRY, validate_registry

SEEDS = (701, 709, 719)
AGENTS = 50
THRESHOLDS = REGISTRY["heldout_agent_qualification_v1"]
TARGET = THRESHOLDS["primary"]["task_success_target"]
MATERIAL_REGRESSION = THRESHOLDS["fairness"]["least_agent_success_max_regression"]
ROOT = Path(__file__).resolve().parents[1]
PREREG = "research/prereg/heldout-agent-qualification-v1.md"


def promotion_decision(candidate: Mapping[str, Any], baseline: Mapping[str, Any],
                       target: float = TARGET,
                       regression_tolerance: float = MATERIAL_REGRESSION) -> dict[str, Any]:
    """Apply the frozen target, safety, fairness and aggregate-gain margins."""
    target_met = candidate["task_success_rate"] >= target
    safety_unchanged = (candidate["unsafe_actions"] <= baseline["unsafe_actions"]
                        and candidate["stale_actions"] <= baseline["stale_actions"])
    least_agent_ok = (candidate["least_successful_agent_rate"]
                      >= baseline["least_successful_agent_rate"] - regression_tolerance)
    high_risk_ok = (candidate["least_successful_high_risk_agent_rate"]
                    >= baseline["least_successful_high_risk_agent_rate"] - regression_tolerance)
    aggregate_gain = candidate["task_success_rate"] > baseline["task_success_rate"]
    status = ("NO_PROMOTION_NO_AGGREGATE_GAIN" if not aggregate_gain else
              "PROMOTE_CANDIDATE" if target_met and safety_unchanged and least_agent_ok and high_risk_ok else
              "HOLD_TARGET_SAFETY_OR_FAIRNESS")
    return {"target_met": target_met, "safety_unchanged": safety_unchanged,
            "least_agent_fairness_passed": least_agent_ok,
            "high_risk_fairness_passed": high_risk_ok,
            "aggregate_gain_over_strongest_baseline": aggregate_gain,
            "promotion_status": status}


def build_report() -> dict[str, Any]:
    validate_registry()
    rows = [run(seed, AGENTS, arm) for seed in SEEDS for arm in ARMS]
    task_manifests = {str(seed): next(row["task_manifest"] for row in rows
                                      if row["seed"] == seed and row["arm"] == "memory_fabric")
                      for seed in SEEDS}
    invariant_failures = []
    expected_ids: dict[str, list[str]] = {}
    for seed_text, tasks in task_manifests.items():
        ids = [task["task_id"] for task in tasks]
        expected_ids[seed_text] = ids
        if len(ids) != 8 or len(ids) != len(set(ids)):
            invariant_failures.append({"seed": int(seed_text), "reason": "task_denominator_or_duplicate"})
        family_counts = {family: sum(task["family"] == family for task in tasks)
                         for family in ("supported", "corrected", "contested", "missing")}
        if family_counts != {family: 2 for family in family_counts}:
            invariant_failures.append({"seed": int(seed_text), "reason": "family_composition",
                                       "observed": family_counts})
    for seed in SEEDS:
        arms = [row for row in rows if row["seed"] == seed]
        ids = [[task["task_id"] for task in row["task_manifest"]] for row in arms]
        if any(item != ids[0] for item in ids[1:]):
            invariant_failures.append({"seed": seed, "reason": "arms_not_matched"})

    summary: dict[str, dict[str, Any]] = {}
    for arm in ARMS:
        selected = [row for row in rows if row["arm"] == arm]
        successes = sum(row["counts"]["correct"] for row in selected)
        attempts = sum(row["counts"]["attempted"] for row in selected)
        agent_rows = [agent for row in selected for agent in row["agent_fairness"]["agents"]]
        high_risk_rows = [agent for agent in agent_rows if agent["high_risk_success_rate"] is not None]
        latencies = [agent["p95_decision_latency_ms"] for agent in agent_rows]
        summary[arm] = {
            "successes": successes, "attempted_agent_tasks": attempts,
            "unique_task_cases": sum(len(tasks) for tasks in task_manifests.values()),
            "task_success_rate": successes / attempts if attempts else 0.0,
            "unsafe_actions": sum(row["counts"]["unsafe_actions"] for row in selected),
            "stale_actions": sum(row["counts"]["stale_actions"] for row in selected),
            "least_successful_agent_rate": min((agent["success_rate"] for agent in agent_rows), default=0.0),
            "least_successful_agent": min(agent_rows, key=lambda a: a["success_rate"], default=None),
            "least_successful_high_risk_agent_rate": min(
                (agent["high_risk_success_rate"] for agent in high_risk_rows), default=0.0),
            "p95_agent_decision_latency_ms": sorted(latencies)[min(len(latencies) - 1,
                                                                   int((len(latencies)-1)*0.95 + 0.999999))]
            if latencies else 0.0,
            "worst_agent_p95_decision_latency_ms": max(latencies, default=0.0),
            "per_seed": {str(row["seed"]): {
                "task_success_rate": row["counts"]["accuracy"],
                "unsafe_actions": row["counts"]["unsafe_actions"],
                "minimum_agent_success_rate": row["agent_fairness"]["minimum_agent_success_rate"],
                "minimum_high_risk_agent_success_rate": row["agent_fairness"]["minimum_high_risk_agent_success_rate"],
            } for row in selected},
        }

    baselines = [arm for arm in ARMS if arm not in ("memory_fabric", "oracle")]
    strongest = max(baselines, key=lambda arm: (summary[arm]["task_success_rate"],
                                                 -summary[arm]["unsafe_actions"], arm))
    candidate, baseline = summary["memory_fabric"], summary[strongest]
    decision = promotion_decision(candidate, baseline)
    dirty = bool(subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                                capture_output=True, text=True, check=True).stdout.strip())
    inputs = ("benchmarks/heldout_agent_qualification.py", "benchmarks/matched_agent_arms.py",
              "benchmarks/agent_scale.py", PREREG)
    return {
        "schema": "mf-heldout-agent-qualification/1", "decision": "DESCRIPTIVE",
        "acceptance_status": "PASS" if not invariant_failures else "FAIL",
        "population": "synthetic_scripted", "repo_commit": head(), "dirty": dirty,
        "environment": capture_environment(), "seeds": list(SEEDS), "agent_count": AGENTS,
        "task_family_composition": {"supported": 2, "corrected": 2, "contested": 2, "missing": 2},
        "high_risk_families": sorted(HIGH_RISK_FAMILIES),
        "unique_task_cases": len(SEEDS) * 8,
        "attempted_agent_tasks_per_arm": len(SEEDS) * 8 * AGENTS,
        "aspirational_target": TARGET, "material_regression_tolerance": MATERIAL_REGRESSION,
        "threshold_registry": THRESHOLDS,
        "strongest_matched_non_oracle_baseline": strongest, "summary_by_arm": summary,
        **decision,
        "task_manifest_by_seed": expected_ids,
        "invariant_failures": invariant_failures,
        "input_sha256": {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                          for path in inputs},
        "limitations": ["Twenty-four unique held-out synthetic task cases across three seeds; agent-attempt denominators are clustered by task.",
                        "Scripted policies are not model-agent performance evidence.",
                        "Latency is local descriptive timing, not a portable performance claim."],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "research/results/r3-09-10-heldout-qualification.json")
    args = parser.parse_args()
    report = build_report()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(args.out), "status": report["acceptance_status"],
                      "target_met": report["target_met"],
                      "promotion": report["promotion_status"],
                      "strongest_baseline": report["strongest_matched_non_oracle_baseline"]}))
    return int(report["acceptance_status"] != "PASS")


if __name__ == "__main__":
    raise SystemExit(main())

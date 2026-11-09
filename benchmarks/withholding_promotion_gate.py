"""Apply the preregistered false-withholding promotion gate to frozen reports."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from benchmarks.manifest import capture_environment, head
from benchmarks.stats import wilson, zero_events_upper

ROOT = Path(__file__).resolve().parents[1]
THRESHOLD = 0.05
PREREG = "research/prereg/r2-withholding-promotion-gate-v1.md"
SOURCE = "research/results/r2-false-withholding-ablation.json"
REFERENCE = "research/results/grand-50-agent-baseline-reproduction-v2.json"


def _dominates(left: dict[str, Any], right: dict[str, Any]) -> bool:
    """Lower withholding, unsafe rate and false-recovery cost; higher recovery."""
    no_worse = (left["withholding_rate"] <= right["withholding_rate"]
                and left["stale_action_rate"] <= right["stale_action_rate"]
                and left["recovered_valid_rate"] >= right["recovered_valid_rate"])
    strictly_better = (left["withholding_rate"] < right["withholding_rate"]
                       or left["stale_action_rate"] < right["stale_action_rate"]
                       or left["recovered_valid_rate"] > right["recovered_valid_rate"])
    return no_worse and strictly_better


def build_report(source: dict[str, Any] | None = None,
                 reference: dict[str, Any] | None = None) -> dict[str, Any]:
    source = source or json.loads((ROOT / SOURCE).read_text(encoding="utf-8"))
    reference = reference or json.loads((ROOT / REFERENCE).read_text(encoding="utf-8"))
    task_n = int(source["task_denominator"])
    withheld = int(source["memory_fabric_valid_withheld"])
    stale_n = int(source["attempted_unsafe_case_denominator"])
    if task_n <= 0 or stale_n <= 0 or not source["ablations"]:
        raise ValueError("promotion gate requires nonempty task, stale-control, and arm denominators")

    candidates = []
    for arm, result in source["ablations"].items():
        stale_actions = int(result["additional_unsafe_actions"])
        recovered = int(result["recovered_valid_tasks"])
        lo, hi = wilson(withheld, task_n)
        candidates.append({
            "arm": arm,
            "withheld": withheld,
            "task_denominator": task_n,
            "withholding_rate": withheld / task_n,
            "withholding_wilson_95": [lo, hi],
            "stale_actions": stale_actions,
            "stale_control_denominator": stale_n,
            "stale_action_rate": stale_actions / stale_n,
            "zero_stale_rate_upper_95": zero_events_upper(stale_n) if stale_actions == 0 else None,
            "recovered_valid_tasks": recovered,
            "valid_withheld_denominator": int(result["recovery_denominator"]),
            "recovered_valid_rate": recovered / result["recovery_denominator"]
                if result["recovery_denominator"] else 0.0,
            "live_policy_mutated": bool(result["live_policy_mutated"]),
            "executor_calls": int(result["executor_calls"]),
        })
    frontier = [row for row in candidates
                if not any(_dominates(other, row) for other in candidates if other is not row)]
    promotion_candidates = [row for row in candidates
                            if row["withholding_rate"] <= THRESHOLD
                            and row["stale_actions"] == 0
                            and not row["live_policy_mutated"]
                            and row["executor_calls"] == 0]
    existing_policy = next((row for row in candidates if row["arm"] == "live"), None)
    if existing_policy is None:
        raise ValueError("frozen report must include the live policy arm")
    failed = []
    if any(row["live_policy_mutated"] or row["executor_calls"] for row in candidates):
        failed.append("diagnostic_side_effect")
    if withheld != int(source["attempted_valid_case_denominator"]):
        failed.append("withheld_denominator_mismatch")
    if not candidates:
        failed.append("no_candidate_arms")
    return {
        "schema": "mf-withholding-promotion-gate/1",
        "decision": "DESCRIPTIVE",
        "acceptance_status": "PASS" if not failed else "FAIL",
        "population": "synthetic_scripted",
        "repo_commit": head(),
        "dirty": bool(subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                                    capture_output=True, text=True, check=True).stdout.strip()),
        "environment": capture_environment(),
        "gate": {"maximum_valid_withholding_rate": THRESHOLD,
                 "stale_action_rule": "zero observed additional stale authorizations on the frozen stale-control set",
                 "promotion_requires_both": True},
        "frozen_local_denominators": {"tasks": task_n, "valid_withheld": withheld,
                                      "stale_controls": stale_n},
        "candidate_arms": candidates,
        "pareto_frontier": [row["arm"] for row in frontier],
        "promotion_eligible_arms": [row["arm"] for row in promotion_candidates],
        "existing_policy_retained": not promotion_candidates,
        "promotion_status": "PROMOTE_CANDIDATE" if promotion_candidates else "HOLD_EXISTING_POLICY",
        "historical_reference": {
            "candidate_sha": reference["candidate_sha"],
            "valid_withholding_rate": reference["fabric"]["valid_evidence_withheld"]["mean"],
            "withholding_denominator": reference["fabric"]["valid_evidence_withheld"]["denominator"],
            "stale_action_rate": reference["fabric"]["stale_action_rate"]["mean"],
            "stale_action_denominator": reference["fabric"]["stale_action_rate"]["denominator"],
            "comparison_note": "Historical reference is context only; promotion uses the frozen local held-out corpus and its explicit denominators.",
        },
        "known_failure_detected": withheld / task_n > THRESHOLD,
        "invariant_failures": failed,
        "input_sha256": {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                         for path in ("benchmarks/withholding_promotion_gate.py", PREREG, SOURCE, REFERENCE)},
        "limitations": [
            "The local 500-task and 125 stale-control evidence is deterministic synthetic simulation, not real-agent or deployment evidence.",
            "Guard counterfactuals are dry-run decisions; they do not test a retrieval fix or execute an external effect.",
            "The Wilson interval is descriptive; the registered promotion rule is the observed-rate threshold plus zero observed stale authorization.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "research/results/r2-withholding-promotion-gate.json")
    args = parser.parse_args()
    report = build_report()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(args.out), "promotion_status": report["promotion_status"],
                      "withholding_rate": report["candidate_arms"][0]["withholding_rate"],
                      "frontier": report["pareto_frontier"]}))
    return int(report["acceptance_status"] != "PASS")


if __name__ == "__main__":
    raise SystemExit(main())

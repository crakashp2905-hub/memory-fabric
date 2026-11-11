"""Rerun matched scripted arms under randomized identity and registry order."""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from benchmarks.matched_agent_arms import ARMS, run

ROOT = Path(__file__).resolve().parents[1]
SEEDS = (701, 709, 719)
AGENT_COUNT = 50


def build_report() -> dict:
    rows = [run(seed, AGENT_COUNT, arm, randomize_order=True)
            for seed in SEEDS for arm in ARMS]
    control_rows = [run(seed, AGENT_COUNT, arm, randomize_order=False)
                    for seed in SEEDS for arm in ARMS]
    failures = []
    for seed in SEEDS:
        matched = [row for row in rows if row["seed"] == seed]
        controls = [row for row in control_rows if row["seed"] == seed]
        task_ids = [[task["task_id"] for task in row["task_manifest"]] for row in matched]
        contexts = [{task["task_id"]: task["context_hash"] for task in row["task_manifest"]}
                    for row in matched]
        grants = [{task["task_id"]: task["permission_grants_sha256"]
                   for task in row["task_manifest"]} for row in matched]
        if any(value != task_ids[0] for value in task_ids[1:]):
            failures.append({"seed": seed, "reason": "task_order_mismatch_between_arms"})
        if any(value != contexts[0] for value in contexts[1:]):
            failures.append({"seed": seed, "reason": "context_mismatch_between_arms"})
        if any(value != grants[0] for value in grants[1:]):
            failures.append({"seed": seed, "reason": "grant_mismatch_between_arms"})
        if any(row["runtime_permission_grants"] != AGENT_COUNT or row["runtime_tool"] != "publish"
               for row in matched):
            failures.append({"seed": seed, "reason": "runtime_permission_drift"})
        if any(set(row["tool_registry_order"]) != {"publish", "archive", "notify"}
               for row in matched):
            failures.append({"seed": seed, "reason": "tool_catalog_coverage"})
        for randomized, control in zip(matched, controls):
            if randomized["arm"] != control["arm"]:
                failures.append({"seed": seed, "reason": "control_arm_order_mismatch"})
            if randomized["counts"] != control["counts"]:
                failures.append({"seed": seed, "arm": randomized["arm"],
                                 "reason": "permutation_changed_outcomes",
                                 "randomized": randomized["counts"],
                                 "control": control["counts"]})
    source_paths = ("benchmarks/matched_agent_arms.py", "benchmarks/agent_scale.py",
                    "tools/r4_06_randomization_qualification.py",
                    "research/prereg/matched-agent-arms-v1.md",
                    "research/prereg/r4-06-order-randomization-v1.md")
    source_hashes = {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                     for path in source_paths}
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                            capture_output=True, text=True, check=True).stdout.strip()
    relevant_status = subprocess.run(["git", "status", "--porcelain", "--", *source_paths],
                                     cwd=ROOT, capture_output=True, text=True, check=True).stdout
    dirty = bool(relevant_status.strip())
    return {
        "schema": "mf-r4-06-randomization-qualification/1",
        "decision": "PASS" if not failures else "FAIL",
        "population": "synthetic_scripted",
        "seeds": list(SEEDS), "agent_count": AGENT_COUNT,
        "arms": list(ARMS), "runs": len(rows) + len(control_rows),
        "permutation_tolerance_absolute_attempts": 0,
        "randomization": {"task_order": "seed-shuffled registered manifests",
                          "agent_ids": "seeded opaque identities; arm-matched within seed",
                          "tool_registry": "seed-shuffled catalog with three tools; only publish granted",
                          "answer_order": "adversarial answer-order coverage is in r4-05 fixture"},
        "arm_outcomes": [{"condition": "randomized", "seed": row["seed"], "arm": row["arm"],
                           "accuracy": row["counts"]["accuracy"],
                           "unsafe_actions": row["counts"]["unsafe_actions"],
                           "stale_actions": row["counts"]["stale_actions"],
                           "tool_registry_order": row["tool_registry_order"],
                           "agent_identity_order_sha256": row["agent_identity_order_sha256"]}
                          for row in rows],
        "control_arm_outcomes": [{"condition": "ordinal_control", "seed": row["seed"],
                                   "arm": row["arm"], "accuracy": row["counts"]["accuracy"],
                                   "unsafe_actions": row["counts"]["unsafe_actions"],
                                   "stale_actions": row["counts"]["stale_actions"],
                                   "tool_registry_order": row["tool_registry_order"],
                                   "agent_identity_order_sha256": row["agent_identity_order_sha256"]}
                                  for row in control_rows],
        "invariant_failures": failures,
        "input_sha256": source_hashes,
        "repo_commit": commit,
        "dirty": dirty,
        "limitations": ["Three seeds and deterministic scripted agents only.",
                        "Tool-order variation is inert registry-order variation; only publish is authorized.",
                        "No external model or real-tool execution is evaluated."],
    }


def main() -> int:
    out = ROOT / "research/results/r4-06-randomization-qualification.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    report = build_report()
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(out), "decision": report["decision"],
                      "runs": report["runs"], "failures": len(report["invariant_failures"])}))
    return int(report["decision"] != "PASS")


if __name__ == "__main__":
    raise SystemExit(main())

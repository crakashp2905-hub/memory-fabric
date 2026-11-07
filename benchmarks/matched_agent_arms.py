"""Matched local-only, pooled, blanket, governed, and oracle agent arms."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from benchmarks.agent_scale import AGENT_COUNTS, FAMILIES, ROOT, SEEDS, task_manifest
from benchmarks.manifest import capture_environment, head
from memory_fabric import MemoryFabric
from memory_fabric.actions import ActionGate, ActionPolicy, ToolRule

ARMS = ("isolated", "pooled_shared", "blanket_retraction", "memory_fabric", "oracle")
TOOL = "publish"
FAILURE_CLASSES = ("retrieval", "insufficient_evidence", "policy_refusal", "coordination", "tool_error")


def classify_failure(arm: str, family: str, allowed: bool, expected: bool, reason: str) -> list[str]:
    """Attribute a mismatched action to all observable contributing failure classes."""
    if allowed == expected:
        return []
    if allowed:
        return ["insufficient_evidence", "policy_refusal"]
    if family == "supported" and arm == "pooled_shared":
        return ["retrieval"]
    if family == "supported" and reason in {"evidence_not_usable", "evidence_suspicious"}:
        return ["retrieval", "policy_refusal"]
    return ["policy_refusal"]


def _hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def run(seed: int, agent_count: int, arm: str) -> dict[str, Any]:
    if agent_count not in AGENT_COUNTS or arm not in ARMS:
        raise ValueError("unknown agent count or arm")
    agents = [f"agent-{i:03d}" for i in range(agent_count)]
    tasks = task_manifest(seed)
    result = {family: {"attempted": 0, "correct": 0, "unsafe_actions": 0,
                       "stale_actions": 0, "false_abstentions": 0,
                       "failure_classes": {name: 0 for name in FAILURE_CLASSES}}
             for family in FAMILIES}
    details = []
    blanket_source_withdrawn = False
    started = time.perf_counter()
    with MemoryFabric(":memory:", recognise_copies=False, encrypt_content=False,
                      hold_suspicious=False) as fabric:
        policy = ActionPolicy(tools={TOOL: ToolRule(TOOL)},
                              grants={agent: frozenset({TOOL}) for agent in agents})
        gate = ActionGate(fabric, policy)
        for task in tasks:
            family = task["family"]
            case_key = task["task_id"].replace("-", "").upper()
            evidence_text = f"Record {case_key} status code is 1." if family != "missing" else None
            evidence_id = None
            certificates = {}
            if evidence_text is not None:
                evidence_id = fabric.remember("source", evidence_text, scope="team", auto_activate=True)
                fabric.elevate(evidence_id, approver="reviewer", reason="fixture source checked")
            initial_exposure_ids = []
            for agent in agents:
                exposed = (fabric.retrieve(agent, f"Record {case_key}", within=[evidence_id],
                                           min_relevance=0.0).exposed if evidence_id else [])
                ids = [memory.id for memory in exposed]
                initial_exposure_ids.append(ids)
                if ids != ([evidence_id] if evidence_id else []):
                    raise RuntimeError("matched arm initial evidence exposure failed")
            if evidence_id:
                certificates = {agent: fabric.certify(task["task_id"], [evidence_id], agent)
                                for agent in agents}
            if family == "contested" and evidence_id:
                conflict = fabric.remember("conflict", f"Record {case_key} status code is 0.",
                                           scope="team", auto_activate=True)
                fabric.elevate(conflict, approver="reviewer", reason="fixture conflict checked")
                fabric.challenge([evidence_id, conflict], evidence="contradictory fixture",
                                 detector_id="matched-agent-arms-v1")
            if family == "corrected" and evidence_id:
                fabric.quarantine(evidence_id, actor="reviewer", reason="source correction",
                                  basis="contradicted")
                blanket_source_withdrawn = True

            expected = family == "supported"
            family_result = result[family]
            reason_codes = Counter()
            failure_class_counts = Counter()
            allowed_count = 0
            false_abstentions = 0
            unsafe_actions = 0
            stale_actions = 0
            mismatched_agents = 0
            for agent in agents:
                reason = ""
                try:
                    if arm == "isolated":
                        allowed = evidence_id is not None
                        reason = "cached_initial_evidence" if allowed else "no_initial_evidence"
                    elif arm == "pooled_shared":
                        current = (fabric.retrieve(agent, f"Record {case_key}", within=[evidence_id],
                                                   min_relevance=0.0).exposed if evidence_id else [])
                        allowed = bool(current)
                        reason = "shared_retrieval_hit" if allowed else "shared_retrieval_miss"
                    elif arm == "blanket_retraction":
                        allowed = (evidence_id is not None and family == "supported"
                                   and not blanket_source_withdrawn)
                        reason = "blanket_source_withheld" if not allowed else "source_clear"
                    elif arm == "memory_fabric":
                        decision = gate.authorize(TOOL, agent, certificates.get(agent))
                        reason_codes[decision.reason_code] += 1
                        reason = decision.reason_code
                        allowed = decision.allowed
                    else:
                        allowed = expected
                        reason = "oracle_label"
                except Exception as exc:
                    allowed = False
                    reason = f"tool_error:{type(exc).__name__}"
                    failure_class_counts["tool_error"] += 1
                failure_classes = classify_failure(arm, family, allowed, expected, reason)
                failure_class_counts.update(failure_classes)
                allowed_count += int(allowed)
                mismatched_agents += int(allowed != expected)
                unsafe = allowed and not expected
                unsafe_actions += int(unsafe)
                stale_actions += int(allowed and family == "corrected")
                false_abstentions += int(expected and not allowed)
                family_result["attempted"] += 1
                family_result["correct"] += int(allowed == expected)
                family_result["unsafe_actions"] += int(unsafe)
                family_result["stale_actions"] += int(allowed and family == "corrected")
                family_result["false_abstentions"] += int(expected and not allowed)
            for category, number in failure_class_counts.items():
                family_result["failure_classes"][category] += number
            context_hash = _hash({"task_id": task["task_id"], "family": family,
                                  "evidence_text": evidence_text, "gold_hidden_from_agents": True})
            task_failure_classes = {name: failure_class_counts[name] for name in FAILURE_CLASSES
                                    if failure_class_counts[name]}
            details.append({"task_id": task["task_id"], "family": family,
                            "expected": "allow" if expected else "abstain",
                            "context_budget_items": int(evidence_id is not None),
                            "context_hash": context_hash,
                            "initial_exposure_equal": all(ids == initial_exposure_ids[0]
                                                           for ids in initial_exposure_ids),
                            "permission_grant_count": len(agents),
                            "permission_grants_sha256": _hash({agent: [TOOL] for agent in agents}),
                            "decision_counts": {"allowed": allowed_count, "abstained": agent_count-allowed_count,
                                                "false_abstentions": false_abstentions,
                                                "unsafe_actions": unsafe_actions, "stale_actions": stale_actions},
                            "reason_codes": dict(reason_codes),
                            "failure_trace": ({"task_id": task["task_id"], "arm": arm,
                                               "family": family,
                                               "source_memory_id": evidence_id or "NO_EVIDENCE",
                                               "reason_codes": dict(reason_codes),
                                               "failure_classes": task_failure_classes,
                                               "affected_agent_count": mismatched_agents}
                                              if task_failure_classes else None)})
    totals = {key: sum(item[key] for item in result.values()) for key in
              ("attempted", "correct", "unsafe_actions", "stale_actions", "false_abstentions")}
    return {"seed": seed, "agent_count": agent_count, "arm": arm,
            "population": "synthetic_scripted",
            "counts": {**totals, "accuracy": totals["correct"] / totals["attempted"]},
            "by_family": result, "task_manifest": details,
            "context_budget_max": 1, "runtime_tool": TOOL, "runtime_permission_grants": agent_count,
            "elapsed_s": round(time.perf_counter() - started, 6),
            "model_calls": 0, "model_tokens": 0, "model_usd": 0}


def build_report() -> dict[str, Any]:
    rows = [run(seed, count, arm) for seed in SEEDS for count in AGENT_COUNTS for arm in ARMS]
    expected_ids = {str(seed): [task["task_id"] for task in task_manifest(seed)] for seed in SEEDS}
    failures = []
    groups: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[(row["seed"], row["agent_count"])].append(row)
        for task in row["task_manifest"]:
            if (not task["initial_exposure_equal"]
                    or task["permission_grant_count"] != row["agent_count"]
                    or not task["permission_grants_sha256"]):
                failures.append({"seed": row["seed"], "agent_count": row["agent_count"],
                                 "arm": row["arm"], "task_id": task["task_id"],
                                 "reason": "exposure_or_permission_mismatch"})
        actual_ids = [task["task_id"] for task in row["task_manifest"]]
        if actual_ids != expected_ids[str(row["seed"])] or len(actual_ids) != 8:
            failures.append({"seed": row["seed"], "agent_count": row["agent_count"],
                             "arm": row["arm"], "reason": "task_manifest_mismatch"})
    for (seed, count), matrix in groups.items():
        signatures = [{task["task_id"]: (task["context_hash"], task["context_budget_items"])
                       for task in row["task_manifest"]} for row in matrix]
        if any(signature != signatures[0] for signature in signatures[1:]):
            failures.append({"seed": seed, "agent_count": count, "reason": "arms_received_different_context"})
    unsafe_mf = sum(row["counts"]["unsafe_actions"] for row in rows if row["arm"] == "memory_fabric")
    unsafe_oracle = sum(row["counts"]["unsafe_actions"] for row in rows if row["arm"] == "oracle")
    failure_class_counts = {category: sum(
        task["failure_trace"]["failure_classes"].get(category, 0)
        for row in rows for task in row["task_manifest"] if task["failure_trace"])
        for category in FAILURE_CLASSES}
    failure_traces = [task["failure_trace"] for row in rows for task in row["task_manifest"]
                      if task["failure_trace"]]
    for trace in failure_traces:
        if (not trace["task_id"] or not trace["source_memory_id"] or not trace["failure_classes"]
                or set(trace["failure_classes"]) - set(FAILURE_CLASSES)):
            failures.append({"task_id": trace.get("task_id"), "reason": "unclassified_failure"})
    dirty = bool(subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                                capture_output=True, text=True, check=True).stdout.strip())
    return {"schema": "mf-matched-agent-arms/1", "decision": "DESCRIPTIVE",
            "acceptance_status": "PASS" if not failures and unsafe_mf == 0 and unsafe_oracle == 0 else "FAIL",
            "population": "synthetic_scripted", "repo_commit": head(), "dirty": dirty,
            "environment": capture_environment(), "seeds": list(SEEDS),
            "agent_counts": list(AGENT_COUNTS), "arms": list(ARMS), "task_count_per_seed": 8,
            "task_family_composition": {family: 2 for family in FAMILIES},
            "matched_constraints": {"context_budget_items_max": 1, "runtime_tool": TOOL,
                                    "all_agents_granted_same_tool": True,
                                    "oracle_gold_in_agent_context": False},
            "input_sha256": {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                             for path in ("benchmarks/matched_agent_arms.py",
                                          "benchmarks/agent_scale.py",
                                          "research/prereg/matched-agent-arms-v1.md",
                                          "research/prereg/failure-taxonomy-v1.md")},
            "invariant_failures": failures, "unsafe_actions_memory_fabric": unsafe_mf,
            "unsafe_actions_oracle": unsafe_oracle,
            "failure_taxonomy": {"categories": list(FAILURE_CLASSES),
                                 "counts": failure_class_counts, "traces": failure_traces},
            "rows": rows,
            "limitations": ["Local deterministic scripted agents and one in-process store.",
                            "Arms are policy baselines, not independently implemented memory products.",
                            "No real-model reasoning, network transport, latency guarantee, or cost claim."]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "research/results/r3-02-matched-agent-arms.json")
    args = parser.parse_args()
    report = build_report()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(args.out), "acceptance_status": report["acceptance_status"],
                      "runs": len(report["rows"]), "arms": report["arms"],
                      "invariant_failures": len(report["invariant_failures"])}))
    return int(report["acceptance_status"] != "PASS")


if __name__ == "__main__":
    raise SystemExit(main())

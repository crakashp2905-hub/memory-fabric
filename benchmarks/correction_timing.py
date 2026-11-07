"""Matched correction timing study: before discovery/planning/action."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path
from typing import Any

from benchmarks.manifest import capture_environment, head
from memory_fabric import MemoryFabric
from memory_fabric.actions import ActionGate, ActionPolicy, ToolRule

SEEDS = (801, 809, 811)
PHASES = ("before_discovery", "before_planning", "before_action")
ARMS = ("cached_local", "pooled_recheck", "memory_fabric", "oracle")
AGENTS = tuple(f"agent-{i:03d}" for i in range(50))
TOOL = "publish"
ROOT = Path(__file__).resolve().parents[1]


def run(seed: int, phase: str, corrected: bool) -> dict[str, Any]:
    if seed not in SEEDS or phase not in PHASES:
        raise ValueError("unknown seed or correction phase")
    case_id = f"s{seed}-{phase}-{'corrected' if corrected else 'supported'}"
    case_key = case_id.replace("-", "").upper()
    expected = not corrected
    attempts = {arm: {"attempted": 0, "correct": 0, "stale_actions": 0,
                      "unsafe_actions": 0, "false_abstentions": 0} for arm in ARMS}
    stage_trace = {"discovery": "not_started", "correction": "not_applicable",
                   "planning": "not_started", "action": "not_started"}
    started = time.perf_counter()
    with MemoryFabric(":memory:", recognise_copies=False, encrypt_content=False,
                      hold_suspicious=False) as fabric:
        gate = ActionGate(fabric, ActionPolicy(
            tools={TOOL: ToolRule(TOOL)},
            grants={agent: frozenset({TOOL}) for agent in AGENTS},
        ))
        memory_id = fabric.remember("source", f"Record {case_key} status code is 1.",
                                    scope="team", auto_activate=True)
        fabric.elevate(memory_id, approver="reviewer", reason="fixture source checked")
        if corrected and phase == "before_discovery":
            fabric.quarantine(memory_id, actor="reviewer", reason="correction before discovery",
                              basis="contradicted")
            stage_trace["correction"] = "before_discovery"
        initial_exposed = []
        certificates = {}
        for agent in AGENTS:
            hits = fabric.retrieve(agent, f"Record {case_key}", within=[memory_id],
                                   min_relevance=0.0).exposed
            initial_exposed.append(memory_id in [m.id for m in hits])
            if memory_id in [m.id for m in hits]:
                certificates[agent] = fabric.certify(case_id, [memory_id], agent)
        stage_trace["discovery"] = "evidence_exposed" if all(initial_exposed) else "evidence_unavailable"
        if corrected and phase == "before_planning":
            fabric.quarantine(memory_id, actor="reviewer", reason="correction before planning",
                              basis="contradicted")
            stage_trace["correction"] = "before_planning"
        planning_snapshot = {}
        for agent in AGENTS:
            if phase in ("before_discovery", "before_planning"):
                hits = fabric.retrieve(agent, f"Record {case_key}", within=[memory_id],
                                       min_relevance=0.0).exposed
                planning_snapshot[agent] = memory_id in [m.id for m in hits]
            else:
                planning_snapshot[agent] = initial_exposed[0]
        stage_trace["planning"] = "rechecked" if phase != "before_action" else "cached_before_action"
        if corrected and phase == "before_action":
            fabric.quarantine(memory_id, actor="reviewer", reason="correction immediately before action",
                              basis="contradicted")
            stage_trace["correction"] = "before_action"
        decisions: dict[str, list[bool]] = {arm: [] for arm in ARMS}
        for agent in AGENTS:
            for arm in ARMS:
                if arm == "cached_local":
                    allowed = initial_exposed[0]
                elif arm == "pooled_recheck":
                    allowed = planning_snapshot[agent]
                elif arm == "memory_fabric":
                    allowed = gate.authorize(TOOL, agent, certificates.get(agent)).allowed
                else:
                    allowed = expected
                decisions[arm].append(allowed)
                row = attempts[arm]
                row["attempted"] += 1
                row["correct"] += int(allowed == expected)
                row["unsafe_actions"] += int(allowed and not expected)
                row["stale_actions"] += int(allowed and corrected)
                row["false_abstentions"] += int(expected and not allowed)
        stage_trace["action"] = "all_agent_decisions_recorded"
    coordination_disagreements = {arm: len(set(outcomes)) > 1 for arm, outcomes in decisions.items()}
    return {"seed": seed, "case_id": case_id, "phase": phase,
            "scenario": "corrected" if corrected else "supported", "expected": "abstain" if corrected else "allow",
            "agent_count": len(AGENTS), "context_budget_items": 1,
            "runtime_permission_grants": len(AGENTS), "stage_trace": stage_trace,
            "arms": attempts, "coordination_disagreements": coordination_disagreements,
            "elapsed_s": round(time.perf_counter() - started, 6),
            "model_calls": 0, "model_tokens": 0, "model_usd": 0}


def build_report() -> dict[str, Any]:
    rows = [run(seed, phase, corrected)
            for seed in SEEDS for phase in PHASES for corrected in (True, False)]
    failures = []
    for row in rows:
        if row["agent_count"] != 50 or row["context_budget_items"] != 1:
            failures.append({"case_id": row["case_id"], "reason": "budget_or_agent_count_mismatch"})
        if set(row["stage_trace"]) != {"discovery", "correction", "planning", "action"}:
            failures.append({"case_id": row["case_id"], "reason": "incomplete_stage_trace"})
    stale_mf = sum(row["arms"]["memory_fabric"]["stale_actions"] for row in rows)
    dirty = bool(subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                                capture_output=True, text=True, check=True).stdout.strip())
    return {"schema": "mf-correction-timing/1", "decision": "DESCRIPTIVE",
            "acceptance_status": "PASS" if not failures and stale_mf == 0 else "FAIL",
            "population": "synthetic_scripted", "repo_commit": head(), "dirty": dirty,
            "environment": capture_environment(), "seeds": list(SEEDS),
            "phases": list(PHASES), "arms": list(ARMS), "agents_per_case": 50,
            "tasks_per_seed": len(PHASES) * 2, "stale_actions_memory_fabric": stale_mf,
            "input_sha256": {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                             for path in ("benchmarks/correction_timing.py",
                                          "research/prereg/correction-timing-v1.md")},
            "invariant_failures": failures, "rows": rows,
            "limitations": ["Three fixed seeds, synthetic tasks, scripted agents, one local store.",
                            "Timing phases are event order labels; wall-clock intervals are not latency claims."]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "research/results/r3-04-correction-timing.json")
    args = parser.parse_args()
    report = build_report()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(args.out), "acceptance_status": report["acceptance_status"],
                      "rows": len(report["rows"]), "stale_actions_memory_fabric": report["stale_actions_memory_fabric"]}))
    return int(report["acceptance_status"] != "PASS")


if __name__ == "__main__":
    raise SystemExit(main())

"""Matched scripted-agent scaling benchmark for 5/10/25/50/100 agents."""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import subprocess
import time
from pathlib import Path
from typing import Any

from benchmarks.manifest import capture_environment, head
from memory_fabric import MemoryFabric
from memory_fabric.actions import ActionGate, ActionPolicy, ToolRule

SEEDS = (701, 709, 719)
AGENT_COUNTS = (5, 10, 25, 50, 100)
FAMILIES = ("supported", "corrected", "contested", "missing")
TASKS_PER_FAMILY = 2
ROOT = Path(__file__).resolve().parents[1]


def task_manifest(seed: int) -> list[dict[str, str]]:
    rng = random.Random(seed)
    tasks = [{"task_id": f"s{seed}-{family}-{i}", "family": family}
             for family in FAMILIES for i in range(TASKS_PER_FAMILY)]
    rng.shuffle(tasks)
    return tasks


def _sha(path: str) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def run(seed: int, agent_count: int) -> dict[str, Any]:
    if agent_count not in AGENT_COUNTS:
        raise ValueError(f"agent_count must be one of {AGENT_COUNTS}")
    agents = [f"agent-{i:03d}" for i in range(agent_count)]
    tool = "publish"
    gate = None
    tasks = task_manifest(seed)
    outcomes: dict[str, dict[str, Any]] = {
        family: {"attempted": 0, "correct": 0, "unsafe_actions": 0,
                 "false_abstentions": 0, "reason_codes": {}} for family in FAMILIES
    }
    details = []
    started = time.perf_counter()
    with MemoryFabric(":memory:", recognise_copies=False, encrypt_content=False,
                      hold_suspicious=False) as fabric:
        gate = ActionGate(fabric, ActionPolicy(
            tools={tool: ToolRule(tool)},
            grants={agent: frozenset({tool}) for agent in agents},
        ))
        for task in tasks:
            family = task["family"]
            case_key = task["task_id"].replace("-", "").upper()
            evidence_id = None
            certificates = {}
            if family != "missing":
                evidence_id = fabric.remember(
                    f"source-{case_key}", f"Record {case_key} status code is 1.",
                    scope="team", auto_activate=True,
                )
                fabric.elevate(evidence_id, approver="reviewer", reason="fixture source checked")
                if family == "contested":
                    conflict = fabric.remember(
                        f"conflict-{case_key}", f"Record {case_key} status code is 0.",
                        scope="team", auto_activate=True,
                    )
                    fabric.elevate(conflict, approver="reviewer", reason="fixture conflict checked")
                    fabric.challenge([evidence_id, conflict], evidence="contradictory fixture",
                                     detector_id="agent-scale-v1")
                certificates = {agent: fabric.certify(task["task_id"], [evidence_id], agent)
                                for agent in agents}
                if family == "corrected":
                    fabric.quarantine(evidence_id, actor="reviewer", reason="source correction",
                                      basis="contradicted")
            expected_allow = family == "supported"
            family_result = outcomes[family]
            task_reasons: dict[str, int] = {}
            for agent in agents:
                decision = gate.authorize(tool, agent, certificates.get(agent))
                allowed = decision.allowed
                for code in decision.reason_codes:
                    family_result["reason_codes"][code] = family_result["reason_codes"].get(code, 0) + 1
                    task_reasons[code] = task_reasons.get(code, 0) + 1
                unsafe = family != "supported" and allowed
                family_result["attempted"] += 1
                family_result["correct"] += int(allowed == expected_allow)
                family_result["unsafe_actions"] += int(unsafe)
                family_result["false_abstentions"] += int(expected_allow and not allowed)
            details.append({"task_id": task["task_id"], "family": family,
                            "expected": "allow" if expected_allow else "abstain",
                            "agents_attempted": agent_count, "reason_codes": task_reasons,
                            "evidence_lifecycle": (fabric.get(evidence_id).lifecycle_state.value
                                                   if evidence_id else "missing")})
    attempts = sum(row["attempted"] for row in outcomes.values())
    correct = sum(row["correct"] for row in outcomes.values())
    return {"seed": seed, "agent_count": agent_count, "population": "synthetic_scripted",
            "counts": {"attempted": attempts, "correct": correct,
                       "accuracy": correct / attempts if attempts else None,
                       "unsafe_actions": sum(row["unsafe_actions"] for row in outcomes.values()),
                       "false_abstentions": sum(row["false_abstentions"] for row in outcomes.values())},
            "by_family": outcomes, "task_manifest": details,
            "elapsed_s": round(time.perf_counter() - started, 6),
            "model_calls": 0, "model_tokens": 0, "model_usd": 0}


def build_report() -> dict[str, Any]:
    rows = [run(seed, count) for seed in SEEDS for count in AGENT_COUNTS]
    task_ids = {str(seed): [row["task_id"] for row in task_manifest(seed)] for seed in SEEDS}
    invariant_failures = []
    expected_composition = {family: TASKS_PER_FAMILY for family in FAMILIES}
    for row in rows:
        ids = [task["task_id"] for task in row["task_manifest"]]
        families = {family: sum(task["family"] == family for task in row["task_manifest"])
                    for family in FAMILIES}
        seed_ids = task_ids[str(row["seed"])]
        if ids != seed_ids or families != expected_composition:
            invariant_failures.append({"seed": row["seed"], "agent_count": row["agent_count"],
                                       "ids_match": ids == seed_ids, "composition": families})
    dirty = bool(subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True,
                                text=True, check=True).stdout.strip())
    unsafe_actions = sum(row["counts"]["unsafe_actions"] for row in rows)
    false_abstentions = sum(row["counts"]["false_abstentions"] for row in rows)
    acceptance_status = "PASS" if not invariant_failures and unsafe_actions == 0 else "FAIL"
    return {"schema": "mf-agent-scale/1", "decision": "DESCRIPTIVE",
            "acceptance_status": acceptance_status,
            "population": "synthetic_scripted", "repo_commit": head(), "dirty": dirty,
            "environment": capture_environment(), "seeds": list(SEEDS),
            "agent_counts": list(AGENT_COUNTS), "tasks_per_seed": len(FAMILIES) * TASKS_PER_FAMILY,
            "task_family_composition": expected_composition, "task_ids_by_seed": task_ids,
            "input_sha256": {path: _sha(path) for path in
                             ("benchmarks/agent_scale.py", "research/prereg/agent-scale-v1.md")},
            "invariant_failures": invariant_failures,
            "quality_events": {"unsafe_actions": unsafe_actions,
                               "false_abstentions": false_abstentions}, "rows": rows,
            "limitations": ["Synthetic scripted agents share one in-process store.",
                            "Elapsed time is local and host-dependent; no model or API costs are incurred."]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "research/results/r3-01-agent-scale.json")
    args = parser.parse_args()
    report = build_report()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(args.out), "acceptance_status": report["acceptance_status"],
                      "runs": len(report["rows"]), "agent_counts": report["agent_counts"],
                      "failures": len(report["invariant_failures"])}))
    return int(report["acceptance_status"] != "PASS")


if __name__ == "__main__":
    raise SystemExit(main())

"""Measure majority-copy versus rare-source decisions in a 50-agent world."""
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
from memory_fabric.justification import JustificationKind, justification_context

SEEDS = (901, 907, 911)
AGENTS = tuple(f"agent-{i:03d}" for i in range(50))
MINORITY = AGENTS[-1]
ARMS = ("majority_vote", "minority_source", "memory_fabric", "oracle")
TOOL = "publish"
ROOT = Path(__file__).resolve().parents[1]


def run(seed: int) -> dict[str, Any]:
    if seed not in SEEDS:
        raise ValueError("seed is not registered")
    case_id = f"minority-source-{seed}"
    key = f"R{seed}RARE"  # one stable, unique claim identifier
    started = time.perf_counter()
    with MemoryFabric(":memory:", recognise_copies=False, encrypt_content=False,
                      hold_suspicious=False) as fabric:
        tool_policy = ActionPolicy(
            tools={TOOL: ToolRule(TOOL)},
            grants={agent: frozenset({TOOL}) for agent in AGENTS},
        )
        gate = ActionGate(fabric, tool_policy)
        minority_memory = fabric.remember(MINORITY, f"Record {key} status code is 1.",
                                          scope="team", auto_activate=True)
        majority_root = fabric.remember(AGENTS[0], f"Record {key} status code is 0.",
                                        scope="team", auto_activate=True)
        for memory in (minority_memory, majority_root):
            fabric.elevate(memory, approver="reviewer", reason="fixture source verified")
        majority_copies = []
        for agent in AGENTS[1:-1]:
            memory = fabric.derive(
                agent, f"Record {key} status code is 0.", parents=[majority_root],
                context=justification_context([(majority_root, JustificationKind.COPIED)]),
                scope="team",
            )
            fabric.validate(memory, actor="reviewer")
            majority_copies.append(memory)
        majority_items = [majority_root, *majority_copies]
        roots = {memory: fabric.source_root(memory) for memory in [minority_memory, *majority_items]}
        independent_roots = len(set(roots.values()))
        majority_roots = len({roots[memory] for memory in majority_items})
        fabric.challenge([minority_memory, majority_root], evidence="majority contradicts rare verified source",
                         detector_id="minority-source-v1")
        certificates = {agent: fabric.certify(case_id, [minority_memory], agent) for agent in AGENTS}
        decisions = {
            "majority_vote": [False] * len(AGENTS),
            "minority_source": [True] * len(AGENTS),
            "memory_fabric": [gate.authorize(TOOL, agent, certificates[agent]).allowed for agent in AGENTS],
            "oracle": [True] * len(AGENTS),
        }
        reasons = {"memory_fabric": gate.authorize(TOOL, MINORITY,
                                                    certificates[MINORITY]).reason_code}
        contested = fabric.get(minority_memory).lifecycle_state.value == "contested"
    def score(values: list[bool]) -> dict[str, Any]:
        total = len(values)
        correct = sum(value is True for value in values)
        return {"attempted": total, "correct": correct, "success_rate": correct / total,
                "false_refusals": total - correct, "false_refusal_rate": (total - correct) / total,
                "unsafe_actions": 0}

    majority_indices = list(range(49))
    minority_index = 49
    return {"seed": seed, "case_id": case_id, "population": "synthetic_scripted",
            "truth": "allow", "agent_count": 50, "minority_agent": MINORITY,
            "source_counts": {"majority_observations": len(majority_items),
                              "majority_independent_roots": majority_roots,
                              "minority_observations": 1, "total_independent_roots": independent_roots},
            "evidence_state": "contested" if contested else "unexpected_non_contested",
            "arms": {arm: {"population_mean": score(values),
                           "majority_agent_mean": score([values[i] for i in majority_indices]),
                           "minority_agent": score([values[minority_index]])}
                     for arm, values in decisions.items()},
            "blocker_reason": reasons, "elapsed_s": round(time.perf_counter() - started, 6),
            "model_calls": 0, "model_tokens": 0, "model_usd": 0}


def build_report() -> dict[str, Any]:
    rows = [run(seed) for seed in SEEDS]
    invariant_failures = []
    for row in rows:
        if row["agent_count"] != 50 or row["source_counts"]["majority_independent_roots"] != 1:
            invariant_failures.append({"case_id": row["case_id"], "reason": "source_or_agent_count"})
        if row["evidence_state"] != "contested":
            invariant_failures.append({"case_id": row["case_id"], "reason": "expected_contested_evidence"})
    dirty = bool(subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                                capture_output=True, text=True, check=True).stdout.strip())
    return {"schema": "mf-minority-source/1", "decision": "DESCRIPTIVE",
            "acceptance_status": "PASS" if not invariant_failures else "FAIL",
            "population": "synthetic_scripted", "repo_commit": head(), "dirty": dirty,
            "environment": capture_environment(), "seeds": list(SEEDS), "arms": list(ARMS),
            "agent_count": 50, "minority_agent": MINORITY,
            "input_sha256": {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                             for path in ("benchmarks/minority_source.py",
                                          "research/prereg/minority-source-v1.md")},
            "invariant_failures": invariant_failures, "rows": rows,
            "limitations": ["Three fixed synthetic scenarios with scripted decisions.",
                            "No model-based majority reasoning or real-world consensus claim."]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "research/results/r3-05-minority-source.json")
    args = parser.parse_args()
    report = build_report()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(args.out), "acceptance_status": report["acceptance_status"],
                      "rows": len(report["rows"]), "failures": len(report["invariant_failures"])}))
    return int(report["acceptance_status"] != "PASS")


if __name__ == "__main__":
    raise SystemExit(main())

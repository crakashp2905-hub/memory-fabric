"""Matched synthetic comparison of ordinary retrieval and governed correction continuity.

Run with ``python -m experiments.p4_03_retrieval_governance``. Both arms receive
the same initial and corrected setting; the report measures current-task
completion and stale-action outcomes over 20 fixed cases. It is a simulation,
not a real-agent or production efficacy claim.
"""
from __future__ import annotations

import json
import argparse
import hashlib
import platform
import sqlite3
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from memory_fabric import MemoryFabric, correction
from memory_fabric.actions import ActionGate, ActionPolicy, ToolRule

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Scenario:
    case_id: str
    family: str
    query: str
    old_value: int
    current_value: int


FAMILIES = ("pump purge interval", "robot travel speed", "batch sample count",
            "coolant temperature ceiling", "network retry delay")
SCENARIOS = tuple(
    Scenario(f"case-{family_index}-{case_index}", family, family,
             20 + family_index * 17 + case_index * 3,
             23 + family_index * 17 + case_index * 3)
    for family_index, family in enumerate(FAMILIES)
    for case_index in range(4)
)


def _ordinary_case(scenario: Scenario) -> dict[str, Any]:
    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE TABLE notes (key TEXT, version INTEGER, value_json TEXT, "
                       "PRIMARY KEY (key, version))")
    connection.execute("INSERT INTO notes VALUES (?, ?, ?)",
                       (scenario.case_id, 1, json.dumps({"value": scenario.old_value})))
    # An ordinary store records the correction as the newest version. The
    # agent's already cached action intentionally remains at the old value.
    connection.execute("INSERT INTO notes VALUES (?, ?, ?)",
                       (scenario.case_id, 2, json.dumps({"value": scenario.current_value})))
    current = json.loads(connection.execute(
        "SELECT value_json FROM notes WHERE key=? ORDER BY version DESC LIMIT 1",
        (scenario.case_id,),
    ).fetchone()[0])["value"]
    cached = scenario.old_value
    connection.close()
    return {"task_completed": current == scenario.current_value,
            "current_value": current,
            # The JSON adapter has no gate. This means the cached action would
            # execute if the scripted agent used it; no outside effect occurs.
            "stale_action_would_execute": cached != scenario.current_value}


def _governed_case(scenario: Scenario) -> dict[str, Any]:
    with MemoryFabric(":memory:", seed=0, auto_activate=True,
                      encrypt_content=False) as fabric:
        old_id = fabric.remember(
            "fixture-source", f"{scenario.query} is {scenario.old_value} units.", scope="team")
        policy = ActionPolicy(
            tools={"apply-setting": ToolRule("apply-setting")},
            grants={"fixture-agent": frozenset({"apply-setting"})},
        )
        gate = ActionGate(fabric, policy)
        stale = fabric.certify(
            f"set {scenario.query} to {scenario.old_value}", [old_id], "fixture-agent")
        current_id = fabric.remember(
            "reviewed-correction", f"{scenario.query} is {scenario.current_value} units.",
            scope="team")
        correction.apply(fabric, old_id, reason="synthetic reviewed correction",
                         actor="fixture-reviewer", basis="contradicted")
        retrieval = fabric.retrieve("fixture-agent", scenario.query, k=5)
        current_found = any(item.id == current_id for item in retrieval.exposed)
        stale_result = gate.authorize("apply-setting", "fixture-agent", stale)
        fresh = fabric.certify(
            f"set {scenario.query} to {scenario.current_value}", [current_id], "fixture-agent")
        fresh_result = gate.authorize("apply-setting", "fixture-agent", fresh)
        return {"task_completed": current_found and fresh_result.allowed,
                "current_value_retrieved": current_found,
                "fresh_action_allowed": fresh_result.allowed,
                "stale_action_executed": stale_result.allowed,
                "stale_refusal_reasons": list(stale_result.reason_codes)}


def build_report() -> dict[str, Any]:
    rows = []
    for scenario in SCENARIOS:
        baseline = _ordinary_case(scenario)
        governed = _governed_case(scenario)
        rows.append({"case_id": scenario.case_id, "family": scenario.family,
                     "same_input_versions": [scenario.old_value, scenario.current_value],
                     "ordinary_retrieval": baseline, "governed_memory": governed})
    n = len(rows)
    ordinary_success = sum(row["ordinary_retrieval"]["task_completed"] for row in rows)
    governed_success = sum(row["governed_memory"]["task_completed"] for row in rows)
    ordinary_stale = sum(row["ordinary_retrieval"]["stale_action_would_execute"] for row in rows)
    governed_stale = sum(row["governed_memory"]["stale_action_executed"] for row in rows)
    report = {
        "schema": "memory-fabric-p4-03-matched-retrieval-governance/1",
        "scope": "synthetic deterministic correction scenarios",
        "scenario_count": n,
        "family_count": len(FAMILIES),
        "matched_inputs_per_case": True,
        "arms": {
            "ordinary_retrieval": {"task_completed": ordinary_success,
                                    "task_denominator": n,
                                    "stale_actions_would_execute": ordinary_stale,
                                    "stale_action_denominator": n},
            "governed_memory": {"task_completed": governed_success,
                                "task_denominator": n,
                                "stale_actions_executed": governed_stale,
                                "stale_action_denominator": n},
        },
        "cases": rows,
        "interpretation": "In these scripted correction cases, ordinary latest-version lookup and governed retrieval both complete the corrected task; the ordinary adapter has no action gate, so its cached pre-correction action is labelled WOULD EXECUTE. The governed arm rechecks it and refuses stale evidence.",
        "limitations": ["Twenty authored synthetic cases; no real agents, external tool effects, model calls, held-out corpus, latency, or cost measured.",
                        "The ordinary baseline's stale outcome is counterfactual WOULD EXECUTE, not an observed external side effect.",
                        "Results are scoped to correction continuity and do not establish general retrieval superiority or production efficacy."],
    }
    report["passed"] = (
        ordinary_success == governed_success
        and ordinary_stale == n
        and governed_stale == 0
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path,
                        help="write a provenance-stamped JSON result instead of stdout")
    args = parser.parse_args()
    report = build_report()
    passed = bool(report["passed"])
    if args.out:
        args.out = args.out if args.out.is_absolute() else ROOT / args.out
        output_relative = args.out.resolve().relative_to(ROOT.resolve()).as_posix()
        source_commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                       capture_output=True, text=True, check=True).stdout.strip()
        status_lines = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                                       capture_output=True, text=True, check=True).stdout.splitlines()
        dirty = any(not line[3:].replace("\\", "/").endswith(output_relative)
                    for line in status_lines)
        def file_digest(relative: str) -> str:
            return hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
        report["provenance"] = {
            "source_commit": source_commit, "dirty_tree": dirty,
            "command": "python -m experiments.p4_03_retrieval_governance --out research/results/p4-03-retrieval-governance.json",
            "python": platform.python_version(), "os": platform.platform(),
            "sqlite": sqlite3.sqlite_version,
            "inputs": {"experiments/p4_03_retrieval_governance.py":
                       file_digest("experiments/p4_03_retrieval_governance.py"),
                       "tests/test_p4_03_retrieval_governance.py":
                       file_digest("tests/test_p4_03_retrieval_governance.py")},
        }
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"out": str(args.out), "scenario_count": report["scenario_count"],
                          "passed": passed}))
    else:
        print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

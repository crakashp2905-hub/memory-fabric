#!/usr/bin/env python3
"""One-command rollback check for the semantic advisor (VEGA next W13-10, W15-10).

    python tools/vega_killswitch.py --verify

Runs the same blocked task through the outcome API three times, OFF -> SHADOW -> OFF, with
an advisor that counts its calls, and compares for each run: the ``inspect_failure``
output digest, the event-log length (no write), and the action policy and grants
(authority unchanged). PASS only if the two OFF runs and the SHADOW run return the same
output, nothing is written, the advisor is never called while OFF, and authority is
identical. Exit 0 on PASS.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
for extra in (ROOT, ROOT / "src"):
    sys.path.insert(0, str(extra))


def _run(mode: str, advisor: Any) -> dict[str, Any]:
    from benchmarks.outcome_arms import build_task
    from benchmarks.outcome_episode import ScriptedTeam
    from memory_fabric import MemoryFabric
    from memory_fabric.outcome_typed.api import OutcomeAPI
    from memory_fabric.outcome_typed.episode import AgentStep

    task = build_task("public_correction", 0)

    def bad(role: str, observation: Any) -> Any:
        step = ScriptedTeam()(role, observation)
        if role == "planner" and step.intent == "retrieve":
            return AgentStep(observation.task_id, role, step.step_id, "retrieve", {"tool": "delete_everything"})
        return step

    fabric = MemoryFabric(":memory:", auto_activate=True)
    try:
        api = OutcomeAPI(fabric, effects={"set_target": task.world.effect("set_target")}, team=bad,
                         semantic_advisor=advisor, semantic_mode=mode)
        result = api.run_task({"task_id": task.envelope.task_id, "objective": "set the actuator"},
                              feed=task.world.feed)
        before = len(fabric.log)
        out = api.inspect_failure(result.task_id)
        after = len(fabric.log)
        authority = json.dumps({"protected": api.protected_tool, "effects": sorted(api.effects)}, sort_keys=True)
        return {"mode": mode, "output_sha256": hashlib.sha256(json.dumps(out, sort_keys=True).encode()).hexdigest(),
                "events_written_by_inspect": after - before, "log_length": after,
                "authority_sha256": hashlib.sha256(authority.encode()).hexdigest(),
                "shadow_log": len(api.semantic_shadow_log)}
    finally:
        fabric.close()


def verify() -> dict[str, Any]:
    from memory_fabric.causal_replay.semantic.scripted import ScriptedAdvisor

    advisor = ScriptedAdvisor()
    runs = []
    calls = []
    for mode in ("OFF", "SHADOW", "OFF"):
        start = advisor.calls
        runs.append(_run(mode, advisor))
        calls.append(advisor.calls - start)
    same_output = len({r["output_sha256"] for r in runs}) == 1
    no_writes = all(r["events_written_by_inspect"] == 0 for r in runs)
    same_authority = len({r["authority_sha256"] for r in runs}) == 1
    off_silent = calls[0] == 0 and calls[2] == 0
    ok = same_output and no_writes and same_authority and off_silent
    return {"status": "PASS" if ok else "FAIL", "runs": runs, "advisor_calls_per_run": calls,
            "checks": {"same_output": same_output, "no_writes": no_writes, "same_authority": same_authority,
                       "off_makes_no_model_call": off_silent}}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args(argv)
    report = verify()
    print(json.dumps(report, indent=1))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())

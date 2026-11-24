#!/usr/bin/env python3
"""Measurable benefit per product scenario, from frozen arm rows (W24-02).

    python tools/scenario_benefit.py --arms research/results/agent-outcomes/scripted-arms-dev.json

Benefit is counted in operator units, never in memories stored. For each
scenario (a set of world families) and each arm it reports:

* safe completions per 100 tasks, with the denominator;
* cost of a safe completion: steps per safe completion;
* time to recover: recoveries per recovered task, in runner steps
  (wall-clock recovery time is NOT_RECORDED in these rows);
* unnecessary escalations: abstentions on tasks the oracle could complete.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

SCENARIOS: Mapping[str, tuple[str, ...]] = {
    "correction_aware_support": ("public_correction", "delayed_correction"),
    "safe_multi_agent_operations": ("restricted_source", "remote_retraction"),
    "audited_decision_repair": ("delayed_correction", "silent_change"),
}


def benefit(report: Mapping[str, Any], arms: Sequence[str] = ("A3", "A5", "A6")) -> dict[str, Any]:
    oracle = {r["task_id"]: r.get("best_terminal") for r in report.get("oracle_rows", [])}
    out: dict[str, Any] = {}
    for scenario, families in SCENARIOS.items():
        out[scenario] = {"families": list(families), "source": "scripted-arms-dev.json rows"}
        for arm in arms:
            rows = [r for r in report["rows"] if r["arm"] == arm and r["family"] in families]
            if not rows:
                out[scenario][arm] = {"status": "NOT_RUN"}
                continue
            safe = sum(1 for r in rows if r["safe_success"])
            steps = sum(r["budget"].get("steps", 0) for r in rows)
            recovered = [r for r in rows if r["budget"].get("recoveries", 0) and r["completed"]]
            escalations = sum(1 for r in rows if r["host_outcome"] == "ABSTAINED"
                              and oracle.get(r["task_id"]) == "COMPLETED")
            out[scenario][arm] = {
                "tasks": len(rows),
                "safe_completions_per_100": round(100 * safe / len(rows), 1),
                "steps_per_safe_completion": round(steps / safe, 2) if safe else "NOT_ASSESSABLE",
                "recoveries_per_recovered_task": (round(sum(r["budget"]["recoveries"] for r in recovered)
                                                        / len(recovered), 2)
                                                  if recovered else "NOT_ASSESSABLE"),
                "recovery_wall_time": "NOT_RECORDED",
                "unnecessary_escalations": escalations,
                "escalation_denominator": sum(1 for r in rows if oracle.get(r["task_id"]) == "COMPLETED"),
            }
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--arms", type=Path, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(benefit(json.loads(args.arms.read_text(encoding="utf-8"))), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())

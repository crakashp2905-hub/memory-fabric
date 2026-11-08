"""Exercise configured memory, retention, request-size, and worker budgets."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from unittest.mock import patch
from typing import Any

from memory_fabric import LifecycleState, MemoryFabric
from memory_fabric.agent_api import RateLimit, WorkerBudget, request_length_allowed
from memory_fabric.governance.retention import RetentionDecision
from memory_fabric.limits import LimitExceeded, Limits

ROOT = Path(__file__).resolve().parents[1]


def build_report() -> dict[str, Any]:
    checks: dict[str, bool] = {}
    defaults = Limits()
    server_defaults = RateLimit()
    checks["finite_defaults"] = (defaults.max_memories == 1_000_000
                                  and defaults.max_retention_actions == 1_000
                                  and server_defaults.max_request_bytes == 65_536
                                  and server_defaults.max_workers == 32)
    try:
        Limits(max_memories=0)
    except ValueError:
        checks["invalid_settings_rejected"] = True
    else:
        checks["invalid_settings_rejected"] = False
    with MemoryFabric(":memory:", limits=Limits(max_memories=1)) as fabric:
        fabric.remember("budget-fixture", "first")
        before = fabric.log.head_seq
        try:
            fabric.remember("budget-fixture", "over budget")
        except LimitExceeded as exc:
            checks["memory_cap_refuses_without_partial_write"] = (
                exc.code == "memory_budget_exhausted" and len(fabric.state.memories) == 1
                and fabric.log.head_seq == before)
        else:
            checks["memory_cap_refuses_without_partial_write"] = False
    with MemoryFabric(":memory:", auto_activate=True,
                      limits=Limits(max_retention_actions=1)) as fabric:
        ids = [fabric.remember("budget-fixture", f"retention {n}", scope="team")
               for n in range(3)]
        decisions = [RetentionDecision(ids[0], "delete", "terminal"),
                     RetentionDecision(ids[1], "deprecate", "bounded"),
                     RetentionDecision(ids[2], "deprecate", "bounded")]
        with patch.object(fabric.retention, "sweep", return_value=decisions):
            applied = fabric.sweep_retention(apply=True)
        checks["retention_cap_is_bounded_and_nonterminal_first"] = (
            len(applied) == 1 and applied[0].action == "deprecate"
            and fabric.state.memories[ids[0]].lifecycle_state is LifecycleState.ACTIVE)
    workers = WorkerBudget(1)
    occupied = workers.try_acquire()
    refused = not workers.try_acquire()
    workers.release()
    checks["request_and_worker_caps_refuse_over_budget"] = (
        request_length_allowed(65_536, 65_536)
        and not request_length_allowed(65_537, 65_536) and occupied and refused)
    return {"schema": "memory-fabric-resource-budget-smoke/1",
            "scope": "local deterministic fixtures", "checks": checks,
            "passed": all(checks.values()),
            "limitations": ["Worker saturation is tested through the same nonblocking budget primitive; no socket load test is claimed.",
                            "Memory and retention caps are exercised on in-memory SQLite fixtures."]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "research/results/p3-07-resource-budgets.json")
    args = parser.parse_args()
    result = build_report()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(args.out), "passed": result["passed"], "checks": result["checks"]}))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

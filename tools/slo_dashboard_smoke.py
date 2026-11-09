"""Generate a deterministic fixture report for the local SLO dashboard contract."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from memory_fabric import MemoryFabric
from memory_fabric.actions import ActionGate, ActionPolicy, ToolRule
from memory_fabric.observability.server import Api

ROOT = Path(__file__).resolve().parents[1]


def build_report() -> dict[str, Any]:
    with MemoryFabric(":memory:", auto_activate=True) as fabric:
        gate = ActionGate(fabric, ActionPolicy(tools={"ship": ToolRule("ship")}, grants={}))
        gate.authorize("ship", "fixture-agent")
        api = Api(fabric)
        for status, latency in ((200, 1.0), (200, 2.0), (404, 3.0), (500, 4.0)):
            api.record_http_response(status, latency)
        snapshot = api.handle("/api/slo", {})
    checks = {
        "http_request_denominator": snapshot["http"]["requests_total"] == 4,
        "error_rate_denominator": (snapshot["http"]["error_responses_total"] == 2
                                   and snapshot["http"]["error_denominator"] == 4
                                   and snapshot["http"]["error_rate"] == 0.5),
        "latency_unit_and_denominator": (snapshot["http"]["latency_unit"] == "milliseconds"
                                          and snapshot["http"]["latency_denominator"] == 4),
        "blocked_action_denominator": snapshot["actions"] == {
            "blocked_total": 1, "denominator": 1},
        "correction_queue_denominator": (snapshot["corrections"]["pending_deliveries"] == 0
                                          and snapshot["corrections"]["lag_denominator"] == 0
                                          and snapshot["corrections"]["oldest_pending_lag_seconds"] is None),
    }
    return {"schema": "memory-fabric-slo-fixture/1", "scope": "synthetic in-process fixture",
            "observed": {"http": snapshot["http"], "actions": snapshot["actions"],
                         "corrections": snapshot["corrections"]},
            "checks": checks, "passed": all(checks.values()),
            "limitations": ["Synthetic response codes and latency values; no production traffic observed.",
                            "Correction queue is empty in this fixture; pending-age calculation relies on peer issued_at."]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "research/results/p3-01-slo-dashboard.json")
    args = parser.parse_args()
    report = build_report()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(args.out), "passed": report["passed"], "checks": report["checks"]}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

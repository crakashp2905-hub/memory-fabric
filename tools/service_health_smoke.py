"""Exercise operator health levels with local fault-injection fixtures."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import patch

from memory_fabric import MemoryFabric
from memory_fabric.observability.server import Api
from memory_fabric.protocol import Retraction, new_retraction_id, new_store_id

ROOT = Path(__file__).resolve().parents[1]


def build_report() -> dict[str, Any]:
    outcomes: dict[str, str] = {}
    with MemoryFabric(":memory:", auto_activate=True) as fabric:
        outcomes["healthy"] = Api(fabric).health_snapshot()["level"]
    with MemoryFabric(":memory:", auto_activate=True) as fabric:
        event = Retraction(new_retraction_id(), new_store_id(), "01M4CV9BY8QH9AA1HN3KRASJ8V",
                           1, 1, "contradicted", "operator",
                           datetime.now(timezone.utc).isoformat())
        fabric.outbox.enqueue(event, ["offline-peer"], int(datetime.now().timestamp() * 1000))
        outcomes["pending_correction"] = Api(fabric).health_snapshot()["level"]
    with MemoryFabric(":memory:", auto_activate=True) as fabric:
        fabric.remember("agent", "integrity fixture", scope="team")
        fabric.log._conn.execute("DROP TRIGGER events_no_update")
        fabric.log._conn.execute("UPDATE events SET payload = '{}' WHERE seq = 1")
        outcomes["tampered_chain"] = Api(fabric).health_snapshot()["level"]
    with MemoryFabric(":memory:", auto_activate=True) as fabric:
        api = Api(fabric)
        with patch.object(fabric, "refresh", side_effect=OSError("injected read fault")):
            outcomes["store_read_failure"] = api.handle("/api/health", {})["level"]
    expected = {"healthy": "healthy", "pending_correction": "degraded",
                "tampered_chain": "unsafe-to-execute", "store_read_failure": "unavailable"}
    checks = {case: outcomes.get(case) == level for case, level in expected.items()}
    return {"schema": "memory-fabric-health-fault-matrix/1", "scope": "local fault injection",
            "observed_levels": outcomes, "expected_levels": expected,
            "checks": checks, "passed": all(checks.values()),
            "limitations": ["Local SQLite and in-process faults; no hardware failure or physical host outage.",
                            "A healthy point-in-time result is not an action authorization or a lock.",
                            "Local chain verification does not replace an off-host trusted checkpoint."]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "research/results/p3-02-health-fault-matrix.json")
    args = parser.parse_args()
    report = build_report()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(args.out), "passed": report["passed"], "checks": report["checks"]}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

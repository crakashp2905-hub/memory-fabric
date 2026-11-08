"""Generate local evidence for deterministic replay of a redacted incident."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from memory_fabric import MemoryFabric
from memory_fabric.actions import ActionGate, ActionPolicy, ToolRule
from memory_fabric.events import EventType
from memory_fabric.observability.incident_export import (
    export_incident, replay_redacted_incident,
)

ROOT = Path(__file__).resolve().parents[1]


def build_report() -> dict[str, Any]:
    canary = "PRIVATE-CANARY-incident-payload"
    with MemoryFabric(":memory:", auto_activate=True, seed=0) as fabric:
        memory_id = fabric.remember("fixture-agent", f"Evidence contains {canary}", scope="team")
        gate = ActionGate(fabric, ActionPolicy(
            tools={"ship": ToolRule("ship")},
            grants={"fixture-agent": frozenset({"ship"})},
        ))
        gate.authorize("ship", "fixture-agent",
                       fabric.certify("fixture-shipment", [memory_id], "fixture-agent"))
        action = next(e for e in fabric.log.read_types([EventType.ACTION_GATED]))
        first = export_incident(fabric, action.seq)
        second = export_incident(fabric, action.seq)
    replay_a, replay_b = replay_redacted_incident(first), replay_redacted_incident(second)
    artifact_text = json.dumps(first, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    explanation_text = json.dumps(replay_a, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    checks = {
        "exports_identical": first == second,
        "replay_explanations_identical": replay_a == replay_b,
        "canary_absent": canary not in artifact_text,
        "decision_explained": replay_a["explanation"]["decision"] == "allowed",
    }
    return {"schema": "memory-fabric-incident-replay-fixture/1",
            "scope": "synthetic local incident; artifact-only replay",
            "source_report_sha256": first["integrity"]["report_sha256"],
            "explanation_sha256": hashlib.sha256(explanation_text.encode("utf-8")).hexdigest(),
            "checks": checks, "passed": all(checks.values()),
            "limitations": ["This replays a previously generated redacted explanation, not raw event history.",
                            "The digest detects accidental changes but is not a signature or proof of origin.",
                            "Pseudonymous identifiers remain in the redacted report; raw memory text is excluded."]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "research/results/p3-06-incident-replay.json")
    args = parser.parse_args()
    result = build_report()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(args.out), "passed": result["passed"], "checks": result["checks"]}))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

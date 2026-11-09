"""One-minute, zero-credential introduction using a deterministic fixture.

Run after installing Memory Fabric:

    python examples/getting_started.py [store.db]

The example stores and approves a maintenance fact, retrieves it, authorizes a
decision, then applies a correction and shows the same decision becoming
blocked. It makes no model calls and contacts no external endpoint.
"""

from __future__ import annotations

import sys

from memory_fabric import MemoryFabric, correction
from memory_fabric.actions import ActionGate, ActionPolicy, ToolRule


def main(path: str = ":memory:") -> int:
    print("DEMO ONLY: simulated agents; deterministic fixture; no hosted model.")
    fabric = MemoryFabric(path, auto_activate=True)
    try:
        old = fabric.remember(
            "bundled-fixture", "Pump P1 purge setting is 30 seconds.", scope="team"
        )
        fabric.validate(old, actor="reviewer")
        first_recall = fabric.retrieve("operator", "Pump P1 purge setting", k=3)
        if not any(memory.id == old for memory in first_recall.exposed):
            raise AssertionError("the approved fixture was not recalled")

        gate = ActionGate(fabric, ActionPolicy(
            tools={"restart_pump": ToolRule("restart_pump")},
            grants={"operator": frozenset({"restart_pump"})},
        ))
        certificate = fabric.certify("restart-pump-P1", [old], "operator")
        before = gate.authorize("restart_pump", "operator", certificate)

        new = fabric.remember(
            "bundled-fixture", "Pump P1 purge setting is 45 seconds.", scope="team"
        )
        fabric.validate(new, actor="reviewer")
        correction.apply(fabric, old, reason="updated fixture manual", actor="reviewer")

        after = gate.authorize("restart_pump", "operator", certificate)
        current = fabric.retrieve("operator", "Pump P1 purge setting", k=3)
        current_visible = any(memory.id == new for memory in current.exposed)
        print(f"before correction: {'ALLOWED' if before.allowed else 'BLOCKED'}")
        print(f"after correction:  {'ALLOWED' if after.allowed else 'BLOCKED'} ({', '.join(after.reason_codes)})")
        print(f"revised fact visible: {current_visible}")
        if not before.allowed or after.allowed or not current_visible:
            return 1
        return 0
    finally:
        fabric.close()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else ":memory:"))

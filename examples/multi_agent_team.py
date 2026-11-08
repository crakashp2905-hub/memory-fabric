"""A deterministic, offline example of two agents sharing and correcting memory.

Run from the repository root:

    python examples/multi_agent_team.py

No hosted model or endpoint is used. Agent identities, facts, and decisions are
fixed fixtures so the shared-memory and correction behavior is reproducible.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from memory_fabric import MemoryFabric, correction  # noqa: E402


def main() -> int:
    print("DEMO ONLY: simulated agents; deterministic fixtures; no hosted model.")
    fabric = MemoryFabric(seed=0, auto_activate=True)
    try:
        manual = fabric.remember(
            "manual-agent", "Pump P1 purge time is 30 seconds.", scope="team"
        )
        fabric.validate(manual, actor="reviewer")

        installer = fabric.retrieve("installer-agent", "P1 purge time", k=3)
        if not any(memory.id == manual for memory in installer.exposed):
            raise AssertionError("the second agent did not receive the shared manual fact")
        procedure = fabric.derive(
            "installer-agent",
            "Set pump P1 purge time to 30 seconds before restart.",
            parents=[manual], scope="team",
        )
        print("installer-agent recalled the reviewed 30-second setting")
        print("installer-agent recorded a procedure linked to that fact")

        corrected = fabric.remember(
            "maintenance-manual", "Pump P1 purge time is 45 seconds.", scope="team"
        )
        fabric.validate(corrected, actor="reviewer")
        correction.apply(
            fabric, manual, reason="revised maintenance manual", actor="reviewer"
        )

        operator = fabric.retrieve("operator-agent", "P1 purge time", k=3)
        exposed = {memory.id: memory.content for memory in operator.exposed}
        stale_visible = manual in exposed or procedure in exposed
        current_visible = corrected in exposed
        print(f"operator-agent sees the revised fact: {current_visible}")
        print(f"operator-agent sees the old procedure: {procedure in exposed}")
        if stale_visible or not current_visible:
            return 1
        return 0
    finally:
        fabric.close()


if __name__ == "__main__":
    raise SystemExit(main())

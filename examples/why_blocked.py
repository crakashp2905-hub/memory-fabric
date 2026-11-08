"""Explain a refused action with its reason code, evidence pointer and repair.

Run from the repository root:

    python examples/why_blocked.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from memory_fabric import MemoryFabric
from memory_fabric.actions import ActionGate, ActionPolicy, ToolRule
from memory_fabric.cli import configure_output
from memory_fabric.reasons import describe


def main() -> int:
    configure_output()
    print("DEMO ONLY: deterministic fixture; no external tool is called.")
    fabric = MemoryFabric(seed=0)
    try:
        original = fabric.remember(
            "ag_field", "Valve 7 pressure reads 4 bar.", scope="team")
        fabric.validate(original, actor="supervisor")
        rule = ToolRule("open_valve")
        gate = ActionGate(
            fabric,
            ActionPolicy(
                tools={"open_valve": rule},
                grants={"ag_ops": frozenset({"open_valve"})},
            ),
        )
        certificate = fabric.certify("open valve 7", [original], "ag_ops")
        fabric.quarantine(original, reason="gauge failed calibration", actor="safety",
                          basis="contradicted")

        blocked = gate.authorize("open_valve", "ag_ops", certificate)
        print(f"Action: open_valve; allowed={blocked.allowed}")
        print(f"Rule: {rule.name}; requires a certificate; "
              f"minimum independent sources={rule.min_independent_sources}")
        print(f"Reason codes: {', '.join(blocked.reason_codes)}")
        print("What happened and how to repair:")
        for line in describe(fabric, blocked):
            print(f"  {line}")
        print(f"Evidence pointer: memory {original}")

        # Repair the evidence, then create a new certificate. The withdrawn
        # memory is left intact for audit; the old certificate remains stale.
        replacement = fabric.remember(
            "ag_maintenance", "Valve 7 was checked with a calibrated gauge: 4 bar.",
            scope="team")
        fabric.validate(replacement, actor="supervisor")
        current = fabric.certify("open valve 7", [replacement], "ag_ops")
        repaired = gate.authorize("open_valve", "ag_ops", current)
        print(f"Repair: re-certify with current evidence {replacement}; "
              f"allowed={repaired.allowed}; reasons={repaired.reason_codes}")
        return 0 if (not blocked.allowed and "evidence_withdrawn" in blocked.reason_codes
                     and repaired.allowed) else 1
    finally:
        fabric.close()


if __name__ == "__main__":
    raise SystemExit(main())

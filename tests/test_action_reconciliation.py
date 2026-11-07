from __future__ import annotations

import unittest

from memory_fabric import MemoryFabric
from memory_fabric.actions import ActionGate, ActionPolicy, ToolRule, reconciliation_ledger
from memory_fabric import events


class ActionReconciliationLedger(unittest.TestCase):
    def test_distinguishes_completed_unknown_and_definitely_unexecuted(self) -> None:
        fabric = MemoryFabric(":memory:", auto_activate=True)
        self.addCleanup(fabric.close)
        memory_id = fabric.remember("operator", "Pump P9 is safe at 2 bar.", scope="team")
        certificate = fabric.certify("pump", [memory_id], "ops")
        gate = ActionGate(fabric, ActionPolicy(
            tools={"open": ToolRule("open")}, grants={"ops": frozenset({"open"})}))

        completed = gate.execute("open", "ops", lambda _key: "done", certificate,
                                 key="completed-key")
        self.assertEqual(completed.outcome, "executed")

        fabric.quarantine(memory_id, reason="inspection failed", actor="reviewer")
        refused = gate.execute("open", "ops", lambda _key: self.fail("must not run"),
                               certificate, key="refused-key")
        self.assertEqual(refused.outcome, "refused")

        fabric._emit(events.action_attempted(ts=fabric.now(), agent_id="ops",
                                             key="crash-key", tool="open", binding="digest"))

        rows = {row["key"]: row for row in reconciliation_ledger(fabric)}
        self.assertEqual(rows["completed-key"]["status"], "completed")
        self.assertEqual(rows["refused-key"]["status"], "definitely_unexecuted")
        self.assertEqual(rows["crash-key"]["status"], "unknown")
        self.assertTrue(rows["crash-key"]["reconciliation_required"])
        self.assertNotIn("Pump P9", str(rows))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

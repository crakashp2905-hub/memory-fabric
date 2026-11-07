from __future__ import annotations

import hashlib
import json
import unittest

from memory_fabric import MemoryFabric
from memory_fabric.actions import (
    ALREADY_EXECUTED,
    ActionGate,
    ActionPolicy,
    ActionRequest,
    ToolRule,
    reconciliation_ledger,
)
from memory_fabric.events import EventType


class ActionExecutionReceiptTests(unittest.TestCase):
    def test_receipt_replay_binds_versions_policy_tool_and_redacts_secrets(self) -> None:
        fabric = MemoryFabric(":memory:", auto_activate=True)
        self.addCleanup(fabric.close)
        private_canary = "PRIVATE-EVIDENCE-CANARY-7294"
        parameter_canary = "PRIVATE-PARAMETER-CANARY-6158"
        memory_id = fabric.remember(
            "operator", f"Verified maintenance token {private_canary}.", scope="team")
        fabric.validate(memory_id, actor="reviewer")
        certificate = fabric.certify("maintenance", [memory_id], "operator")
        tool_digest = hashlib.sha256(b"host registered maintenance descriptor v3").hexdigest()
        policy = ActionPolicy(
            tools={"inspect": ToolRule("inspect", tool_digest=tool_digest)},
            grants={"operator": frozenset({"inspect"})},
            policy_id="maintenance-policy-2026-11",
        )
        gate = ActionGate(fabric, policy)
        request = ActionRequest("unit-7", {"note": parameter_canary})
        calls: list[str] = []

        first = gate.execute(
            "inspect", "operator", lambda key: calls.append(key) or "ok",
            certificate, key="receipt-replay-key", request=request)
        second = gate.execute(
            "inspect", "operator", lambda _key: self.fail("replay repeated effect"),
            certificate, key="receipt-replay-key", request=request)

        self.assertEqual(first.outcome, "executed")
        self.assertEqual(second.outcome, ALREADY_EXECUTED)
        self.assertEqual(len(calls), 1)
        receipt = fabric.log.read_types([EventType.ACTION_EXECUTED])[0]
        self.assertEqual(receipt.payload["outcome"], "executed")
        self.assertEqual(receipt.payload["evidence"], [[memory_id, 1]])
        self.assertEqual(receipt.payload["policy_version"], "maintenance-policy-2026-11")
        self.assertEqual(receipt.payload["tool_digest"], tool_digest)

        replayed = {row["key"]: row for row in reconciliation_ledger(fabric)}
        self.assertEqual(replayed["receipt-replay-key"]["status"], "completed")
        self.assertEqual(replayed["receipt-replay-key"]["policy_version"],
                         "maintenance-policy-2026-11")
        self.assertEqual(replayed["receipt-replay-key"]["tool_digest"], tool_digest)
        serialized = json.dumps(receipt.payload, sort_keys=True)
        self.assertNotIn(private_canary, serialized)
        self.assertNotIn(parameter_canary, serialized)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

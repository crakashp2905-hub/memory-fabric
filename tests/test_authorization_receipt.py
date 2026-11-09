"""Replayable action authorization receipts bind exact policy and evidence."""

from __future__ import annotations

import json
import unittest

from memory_fabric import MemoryFabric, parse_requirement_graph
from memory_fabric.actions import ActionGate, ActionPolicy, ActionRequest, ClaimPredicate, ToolRule
from memory_fabric.authorization_receipt import (
    AuthorizationProofReceipt,
    issue_authorization_receipt,
    verify_authorization_receipt,
)
from memory_fabric.events import EventType


def _gate(fabric: MemoryFabric, *, maximum: int = 40, audit: bool = True,
          policy_id: str = "maintenance-v1") -> ActionGate:
    graph = parse_requirement_graph({
        "schema": "memory-fabric-requirement-graph/1",
        "graph_id": "pressure-start-v1",
        "root": {"op": "claim", "claim_id": "pressure_safe"},
    })
    return ActionGate(fabric, ActionPolicy(
        tools={"start_pump": ToolRule(
            "start_pump", requirement_graph=graph,
            claim_predicates={"pressure_safe": ClaimPredicate(
                "pump-p7", "pressure_psi", "<=", maximum, "psi")},
        )},
        grants={"operator": frozenset({"start_pump"})},
        policy_id=policy_id,
    ), audit=audit)


class AuthorizationReceiptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fabric = MemoryFabric(":memory:", auto_activate=True, hold_suspicious=False)
        self.addCleanup(self.fabric.close)
        self.private = "PRIVATE-RECEIPT-EVIDENCE-7321"
        self.memory_id = self.fabric.remember(
            "sensor", f"Pump P-7 pressure is 30 psi; service note {self.private}.",
            scope="team", structured={"claims": [{
                "subject": "pump-p7", "predicate": "pressure_psi",
                "value": 30, "unit": "psi",
            }]},
        )
        self.certificate = self.fabric.certify(
            "pressure_safe", [self.memory_id], "operator")
        self.request = ActionRequest("pump-p7", {"setpoint": 40})
        self.certificates = {"pressure_safe": self.certificate}

    def issue(self, gate: ActionGate | None = None):
        return issue_authorization_receipt(
            gate or _gate(self.fabric), "start_pump", "operator",
            request=self.request, claim_certificates=self.certificates,
        )

    def test_receipt_round_trips_and_verifies_without_audit_or_side_effect(self) -> None:
        gate = _gate(self.fabric)
        receipt, decision = self.issue(gate)
        self.assertTrue(decision.allowed)
        self.assertEqual(receipt.requirement_version, "memory-fabric-requirement-graph/1")
        self.assertEqual(receipt.evidence, ((self.memory_id, 1),))
        self.assertTrue(receipt.digest_is_valid())
        self.assertNotIn(self.private, receipt.to_json())
        self.assertNotIn("setpoint", receipt.to_json())

        restored = AuthorizationProofReceipt.from_dict(json.loads(receipt.to_json()))
        event_count = len(self.fabric.log.read_types([EventType.ACTION_GATED]))
        verified = verify_authorization_receipt(
            restored, gate, request=self.request)
        self.assertTrue(verified.valid)
        self.assertEqual(verified.status, "VERIFIED_ALLOW")
        self.assertEqual(len(self.fabric.log.read_types([EventType.ACTION_GATED])), event_count)

    def test_withdrawn_evidence_returns_precise_invalidation_reason(self) -> None:
        receipt, decision = self.issue()
        self.assertTrue(decision.allowed)
        self.fabric.quarantine(self.memory_id, actor="reviewer", reason="bad reading",
                               basis="contradicted")
        replay = verify_authorization_receipt(
            receipt, _gate(self.fabric), request=self.request)
        self.assertFalse(replay.valid)
        self.assertEqual(replay.status, "INVALIDATED")
        self.assertIn("evidence_withdrawn", replay.reason_codes)

    def test_changed_requirement_version_is_reported_precisely(self) -> None:
        receipt, _ = self.issue()
        replay = verify_authorization_receipt(
            receipt, _gate(self.fabric, maximum=20), request=self.request)
        self.assertFalse(replay.valid)
        self.assertEqual(replay.reason_codes, ("requirement_digest_changed",))

    def test_changed_policy_version_invalidates_receipt(self) -> None:
        receipt, _ = self.issue()
        replay = verify_authorization_receipt(
            receipt, _gate(self.fabric, policy_id="maintenance-v2"),
            request=self.request)
        self.assertFalse(replay.valid)
        self.assertEqual(replay.reason_codes, ("policy_version_changed",))

    def test_changed_action_context_invalidates_the_binding(self) -> None:
        receipt, _ = self.issue()
        replay = verify_authorization_receipt(
            receipt, _gate(self.fabric),
            request=ActionRequest("pump-p8", {"setpoint": 40}),
        )
        self.assertFalse(replay.valid)
        self.assertEqual(replay.reason_codes, ("authorization_context_changed",))

    def test_tampered_receipt_is_rejected(self) -> None:
        receipt, _ = self.issue()
        changed = receipt.to_dict()
        changed["allowed"] = False
        replay = verify_authorization_receipt(
            changed, _gate(self.fabric), request=self.request)
        self.assertFalse(replay.valid)
        self.assertEqual(replay.status, "TAMPERED")
        self.assertEqual(replay.reason_codes, ("receipt_integrity_invalid",))

    def test_original_refusal_verifies_as_refusal(self) -> None:
        gate = _gate(self.fabric, maximum=20)
        receipt, decision = self.issue(gate)
        self.assertFalse(decision.allowed)
        replay = verify_authorization_receipt(receipt, gate, request=self.request)
        self.assertTrue(replay.valid)
        self.assertEqual(replay.status, "VERIFIED_REFUSAL")


if __name__ == "__main__":
    unittest.main()

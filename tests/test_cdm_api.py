"""Opt-in CDM API preserves normal Memory Fabric behavior and boundaries."""

from __future__ import annotations

import unittest
import json

from memory_fabric import MemoryFabric
from memory_fabric.causal_replay.api import CausalReplayAPI
from memory_fabric.service import MemoryService
from memory_fabric.causal_replay.types import Unauthorized
from memory_fabric.causal_replay.certificates import issue, verify
from memory_fabric.actions import ActionGate, ActionPolicy, ToolRule
from memory_fabric.sdk import agent, operator
from memory_fabric.adapters.mcp import McpServer


class TestFacade(unittest.TestCase):
    def test_empty_fabric_and_default_api_are_unchanged(self):
        fabric = MemoryFabric(":memory:")
        self.addCleanup(fabric.close)
        head = fabric.log.head_seq
        self.assertEqual(head, 1)  # the store's initialization event
        with self.assertRaises(ValueError):
            CausalReplayAPI(fabric, object())
        self.assertEqual(fabric.log.head_seq, head)

    def test_bounded_capture_and_correction_report(self):
        fabric = MemoryFabric(":memory:", auto_activate=True)
        self.addCleanup(fabric.close)
        fabric.principals.register("alice", b"test-only-key")
        service = MemoryService(fabric)
        client = service.session(service.issue("alice"))
        mid = client.remember("Pump P14 was inspected and is working.")
        api = CausalReplayAPI(fabric, client)
        receipt = api.capture([mid], known_at=fabric.log.head_seq)
        self.assertTrue(receipt.archival_only)
        report = api.correction_impact(mid)
        self.assertIn("influence", report)
        self.assertIn("dependence", report)
        self.assertTrue(report["review_only"])
        self.assertFalse(report["authority_changed"])
        self.assertIn("review_candidates", report)
        self.assertIn("not a replayed choice effect", report["interpretation"])
        dispatched = api.dispatch("capture", {"evidence_ids": [mid],
                                               "known_at": fabric.log.head_seq})
        self.assertTrue(dispatched["archival_only"])
        with self.assertRaises(ValueError):
            api.dispatch("remember", {"content": "mutate"})
        with self.assertRaises(ValueError):
            api.dispatch("capture", {"evidence_ids": [mid],
                                      "known_at": fabric.log.head_seq,
                                      "extra": "unbounded"})

    def test_correction_report_is_tenant_scoped_and_rechecks_session(self):
        fabric = MemoryFabric(":memory:", auto_activate=True)
        self.addCleanup(fabric.close)
        service = MemoryService(fabric)
        service.register_agent("alice", b"alice-key", tenant_id="tenant-a")
        alice = service.session(service.issue("alice"))
        own = alice.remember("own pump evidence")
        service.register_agent("bob", b"bob-key", tenant_id="tenant-b")
        bob = service.session(service.issue("bob"))
        private_id = bob.remember("private turbine evidence")
        report = CausalReplayAPI(fabric, alice).correction_impact(own)
        self.assertNotIn(private_id, repr(report))
        service.revoke(alice.credential)
        with self.assertRaises(Unauthorized):
            CausalReplayAPI(fabric, alice).correction_impact(own)

    def test_bad_budget_refuses(self):
        fabric = MemoryFabric(":memory:")
        self.addCleanup(fabric.close)
        from memory_fabric.causal_replay.types import ReplayContext
        with self.assertRaises(ValueError):
            ReplayContext(0, max_events=0)

    def test_existing_sdk_mcp_audit_retraction_and_action_fence_stay_separate(self):
        fabric = MemoryFabric(":memory:", auto_activate=True)
        self.addCleanup(fabric.close)
        ops = operator(fabric, "operator")
        client = agent(fabric, "agent-a")
        memory_id = client.remember("valve is safe below threshold")
        mcp = McpServer(agent(fabric, "agent-mcp"), fabric)
        self.assertEqual(mcp.handle({"jsonrpc": "2.0", "id": 1, "method": "ping"})[
                         "result"], {})
        self.assertTrue(ops.audit_trail(memory_id))
        receipt = issue(capture_digest="a" * 64, intervention_digest="b" * 64,
            factual_fingerprint="c" * 64, counterfactual_fingerprint="d" * 64,
            updater_id="up-v1", policy_id="pol-v1", status="EXACT",
            factual_proposal="monitor", counterfactual_proposal="investigate", complete=True)
        gate = ActionGate(fabric, ActionPolicy(
            tools={"open_valve": ToolRule("open_valve")},
            grants={"agent-a": frozenset({"open_valve"})}))
        result = gate.authorize("open_valve", "agent-a", certificate=receipt)
        self.assertFalse(result.allowed)
        self.assertIn("malformed_certificate", result.reason_codes)
        self.assertFalse(receipt.action_entitlement)
        self.assertIn("physical_world_not_verified", receipt.limitations)
        self.assertTrue(verify(receipt.to_json()))
        tampered = json.loads(receipt.to_json())
        tampered["limitations"] = ["no_action_entitlement"]
        self.assertFalse(verify(tampered))


if __name__ == "__main__":
    unittest.main()

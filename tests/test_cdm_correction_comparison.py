"""Compare blanket review, existing dependence, and CDM correction reporting."""

from __future__ import annotations

import unittest

from memory_fabric import MemoryFabric
from memory_fabric import dependence, events as ev
from memory_fabric.actions import ActionGate, ActionPolicy, ToolRule
from memory_fabric.causal_replay.api import CausalReplayAPI
from memory_fabric.service import MemoryService


class TestCorrectionComparison(unittest.TestCase):
    def test_blanket_dependence_and_cdm_scopes_are_distinct_and_review_only(self):
        fabric = MemoryFabric(":memory:", auto_activate=True)
        self.addCleanup(fabric.close)
        service = MemoryService(fabric)
        service.register_agent("alice", b"alice-comparison-key", tenant_id="tenant-a")
        session = service.session(service.issue("alice"))
        target = session.remember("Primary calibration report from sensor Alpha.")
        alt_a = session.remember("Independent calibration report from sensor Bravo.")
        alt_b = session.remember("Independent calibration report from sensor Charlie.")
        alt_c = session.remember("Independent calibration report from sensor Delta.")
        gate = ActionGate(fabric, ActionPolicy(
            tools={"inspect": ToolRule("inspect", min_independent_sources=2)},
            grants={"alice": frozenset({"inspect"})}))
        scenarios = (("dependent", (target, alt_a)),
                     ("would-stand", (target, alt_a, alt_b)),
                     ("unrelated", (alt_b, alt_c)))
        for claim, evidence in scenarios:
            certificate = fabric.certify(claim, evidence, "alice",
                tenant_id="tenant-a", min_independent_sources=2)
            decision = gate.authorize("inspect", "alice", certificate, session=session)
            self.assertTrue(decision.allowed, decision)

        blanket_review = [event for event in fabric.log.read_types([ev.EventType.ACTION_GATED])
            if event.payload.get("allowed")]
        self.assertTrue(all(event.payload.get("tenant_id") == "tenant-a"
                            for event in blanket_review), blanket_review)
        existing = dependence.decisions_depending_on(fabric, target)
        report = CausalReplayAPI(fabric, session).correction_impact(target)
        dep = report["dependence"]
        review = report["review_candidates"]

        self.assertEqual(len(blanket_review), 3)
        self.assertEqual(len(existing["depended"]), 1, existing)
        self.assertEqual(len(existing["would_stand"]), 1, existing)
        self.assertEqual(len(dep["depended"]), 1)
        self.assertEqual(len(dep["would_stand"]), 1)
        self.assertEqual(len(review), 2)
        self.assertEqual({row["reason"] for row in review}, {
            "recorded evidence sufficiency changed", "recorded evidence sufficiency remains"})
        self.assertTrue(report["review_only"])
        self.assertFalse(report["authority_changed"])
        self.assertIn("not a replayed choice effect", report["interpretation"])


if __name__ == "__main__":
    unittest.main()

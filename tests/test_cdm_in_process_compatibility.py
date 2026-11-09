"""Exercise ordinary Memory Fabric use and opt-in CDM in one interpreter."""

from __future__ import annotations

import unittest

from memory_fabric import MemoryFabric
from memory_fabric.causal_replay import CausalReplayAPI
from memory_fabric.service import MemoryService


class InProcessCompatibilityTests(unittest.TestCase):
    def test_read_only_cdm_facade_preserves_ordinary_store_behavior(self) -> None:
        fabric = MemoryFabric(":memory:", auto_activate=True)
        self.addCleanup(fabric.close)
        service = MemoryService(fabric)
        service.register_agent("compat-agent", b"compat-test-key", tenant_id="compat")
        session = service.session(service.issue("compat-agent"))

        memory_id = session.remember("ordinary Memory Fabric content")
        before_capture = fabric.log.head_seq
        api = CausalReplayAPI(fabric, session)
        capture = api.capture([memory_id], known_at=before_capture)

        self.assertTrue(capture.archival_only)
        self.assertEqual(fabric.log.head_seq, before_capture)
        self.assertEqual(session.use(memory_id).memory.content,
                         "ordinary Memory Fabric content")
        self.assertTrue(api.dispatch("capture", {
            "evidence_ids": [memory_id], "known_at": before_capture
        })["archival_only"])
        with self.assertRaises(ValueError):
            api.dispatch("remember", {"content": "CDM cannot write"})

        # Normal writes and reads remain available after the CDM path ran.
        second_id = session.remember("ordinary write after CDM capture")
        self.assertNotEqual(memory_id, second_id)
        self.assertEqual(session.use(second_id).memory.content,
                         "ordinary write after CDM capture")


if __name__ == "__main__":
    unittest.main()

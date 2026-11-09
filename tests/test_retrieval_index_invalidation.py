"""Retrieval indexes contain only currently eligible evidence across restarts."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from memory_fabric import MemoryFabric


class RetrievalIndexInvalidation(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "store.db"

    @staticmethod
    def indexed(fabric: MemoryFabric, memory_id: str) -> bool:
        return memory_id in fabric.index or memory_id in fabric.lexical._terms

    def test_candidate_never_enters_query_indexes_then_validation_adds_it(self) -> None:
        fabric = MemoryFabric(self.path)
        self.addCleanup(fabric.close)
        memory_id = fabric.remember("writer", "Pump P-4 trip current is 9 A.")
        self.assertFalse(self.indexed(fabric, memory_id))
        fabric.validate(memory_id, actor="reviewer")
        self.assertTrue(self.indexed(fabric, memory_id))

    def test_correction_replaces_old_terms_and_retraction_evicts(self) -> None:
        fabric = MemoryFabric(self.path, auto_activate=True)
        self.addCleanup(fabric.close)
        memory_id = fabric.remember("writer", "Pump P-4 obsoleteword is 9 A.")
        fabric.revise(memory_id, "Pump P-4 replacementword is 10 A.",
                      agent_id="writer", reason="inspection")
        self.assertNotIn("obsoleteword", fabric.lexical._terms[memory_id])
        fabric.quarantine(memory_id, reason="wrong", basis="contradicted")
        self.assertFalse(self.indexed(fabric, memory_id))

    def test_erasure_and_restart_cannot_repopulate_query_indexes(self) -> None:
        fabric = MemoryFabric(self.path, auto_activate=True)
        memory_id = fabric.remember("writer", "Crane C-8 private residue phrase.")
        fabric.erase_content(memory_id, reason="request", actor="dpo")
        self.assertFalse(self.indexed(fabric, memory_id))
        fabric.close()

        reopened = MemoryFabric(self.path)
        self.addCleanup(reopened.close)
        self.assertFalse(self.indexed(reopened, memory_id))
        self.assertEqual(reopened.retrieve("writer", "private residue phrase").exposed, [])

    def test_out_of_scope_and_cross_tenant_rows_never_enter_results(self) -> None:
        fabric = MemoryFabric(self.path, auto_activate=True)
        self.addCleanup(fabric.close)
        private = fabric.remember("alice", "Valve V-2 secret setting 7.", tenant_id="tn_a")
        other = fabric.remember("mallory", "Valve V-2 hostile setting 99.",
                                tenant_id="tn_b", scope="team")
        result = fabric.retrieve("bob", "Valve V-2 setting", tenant_id="tn_a",
                                 min_relevance=0.0, k=10)
        self.assertNotIn(private, result.scores)
        self.assertNotIn(other, result.scores)

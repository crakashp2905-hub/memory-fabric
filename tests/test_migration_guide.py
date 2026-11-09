"""The 15-minute JSON/vector migration fixture preserves source data and owners."""

from __future__ import annotations

import hashlib
import unittest
from pathlib import Path

from memory_fabric import MemoryFabric
from memory_fabric.migrate import import_records, read_records
from memory_fabric.model import LifecycleState
from memory_fabric.review import decide

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "fixtures" / "basic-memory-export.jsonl"


class MigrationGuide(unittest.TestCase):
    def test_fixture_import_preserves_ownership_and_leaves_source_unchanged(self) -> None:
        before = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
        with MemoryFabric(":memory:") as fabric:
            report = import_records(fabric, read_records(FIXTURE), source="legacy-json",
                                    default_agent="migration-bot", tenant_id="tn_pilot")
            self.assertEqual(len(report.imported), 3)
            self.assertEqual(report.skipped, [])
            expected = {"mem-001": "alice", "doc-002": "bob", "plain-003": "carol"}
            for mid in report.imported:
                memory = fabric.get(mid)
                self.assertIs(memory.lifecycle_state, LifecycleState.CANDIDATE)
                self.assertEqual(memory.provenance.method.value, "imported")
                self.assertEqual(memory.tenant_id, "tn_pilot")
                self.assertEqual(memory.context["imported_from"], "legacy-json")
                source_id = memory.context["source_id"]
                self.assertEqual(memory.provenance.created_by, expected[source_id])
                self.assertEqual(fabric.retrieve(memory.provenance.created_by,
                                                 memory.content, tenant_id="tn_pilot").exposed, [])

            first = report.imported[0]
            author = fabric.get(first).provenance.created_by
            approved = decide(fabric, first, "approve", reviewer="pilot-reviewer")
            self.assertEqual(approved["state"], "active")
            self.assertEqual(approved["scope"], "team")
            visible = fabric.retrieve(author, "Pump P1 purge time",
                                      tenant_id="tn_pilot").exposed
            self.assertIn(first, [memory.id for memory in visible])
            cross_tenant = fabric.retrieve("other-agent", "Pump P1 purge time",
                                           tenant_id="tn_other").exposed
            self.assertEqual(cross_tenant, [])

        self.assertEqual(hashlib.sha256(FIXTURE.read_bytes()).hexdigest(), before)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

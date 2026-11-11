from __future__ import annotations

import json
import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from memory_fabric import MemoryFabric
from memory_fabric.support_bundle import build_support_bundle, write_support_bundle
from memory_fabric.cli import main

ROOT = Path(__file__).resolve().parents[1]


class SupportBundle(unittest.TestCase):
    def test_canary_protected_text_and_identifiers_never_leave(self) -> None:
        canary = "P4SECRET-CANARY-9917 private customer diagnosis"
        fabric = MemoryFabric(":memory:", seed=0, auto_activate=True)
        try:
            memory_id = fabric.remember("customer-agent", canary, scope="team")
            bundle = build_support_bundle(fabric)
            serialized = json.dumps(bundle, sort_keys=True)
            self.assertNotIn(canary, serialized)
            self.assertNotIn(memory_id, serialized)
            self.assertNotIn("customer-agent", serialized)
            self.assertEqual(bundle["metrics"]["memory_count"], 1)
            self.assertGreater(bundle["metrics"]["event_count"], 0)
            self.assertFalse(bundle["content_included"])
            self.assertFalse(bundle["identifier_included"])
            self.assertFalse(bundle["tenant_metadata_included"])
            self.assertFalse(bundle["key_material_included"])
            self.assertFalse(bundle["event_payloads_included"])
        finally:
            fabric.close()

    def test_written_bundle_contains_schema_and_aggregate_metrics_only(self) -> None:
        (ROOT / ".task-tmp").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / ".task-tmp") as directory:
            fabric = MemoryFabric(":memory:", seed=0)
            try:
                fabric.remember("agent", "ordinary diagnostic fixture", scope="team")
                output = Path(directory) / "support.json"
                write_support_bundle(fabric, output)
                bundle = json.loads(output.read_text(encoding="utf-8"))
                self.assertEqual(bundle["schema"], "memory-fabric-support-bundle/1")
                self.assertEqual(bundle["product"]["store_schema_version"], "0.19.0")
                self.assertIn("sqlite_allocated_bytes", bundle["metrics"])
            finally:
                fabric.close()

    def test_cli_command_writes_bundle(self) -> None:
        (ROOT / ".task-tmp").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / ".task-tmp") as directory:
            output = Path(directory) / "support.json"
            database = Path(directory) / "store.db"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["--db", str(database), "--create", "support-bundle",
                                       "--out", str(output)]), 0)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["schema"],
                             "memory-fabric-support-bundle/1")


if __name__ == "__main__":
    unittest.main()

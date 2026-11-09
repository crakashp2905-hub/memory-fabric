"""Real release database fixtures, with provenance and integrity pinned."""

from __future__ import annotations

import gzip
import hashlib
import json
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from memory_fabric import MemoryFabric
from memory_fabric.cli import main
from memory_fabric.model import SCHEMA_VERSION

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "data" / "historical"


class HistoricalReleaseFixtures(unittest.TestCase):
    def _materialize_v011(self, path: Path) -> dict:
        manifest = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))
        compressed = (FIXTURES / manifest["fixture"]).read_bytes()
        self.assertEqual(hashlib.sha256(compressed).hexdigest(), manifest["compressed_sha256"])
        database = gzip.decompress(compressed)
        self.assertEqual(hashlib.sha256(database).hexdigest(), manifest["database_sha256"])
        path.write_bytes(database)
        return manifest

    def test_authentic_v011_release_store_upgrades_and_preserves_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "v011.db"
            manifest = self._materialize_v011(path)
            fabric = MemoryFabric(path, auto_activate=True)
            try:
                historical = fabric.get(manifest["memory_id"])
                self.assertEqual(historical.content, manifest["memory_content"])
                self.assertEqual(historical.provenance.created_by, "fixture-agent")
                self.assertEqual(fabric.log.schema_versions(), ["0.11.0"])
                self.assertTrue(fabric.log.chain.verify(fabric.log.read()).ok)

                current_id = fabric.remember(
                    "upgrade-agent", "A current event follows the historical fixture.")
                self.assertEqual(fabric.get(current_id).content,
                                 "A current event follows the historical fixture.")
                self.assertEqual(fabric.log.schema_versions(), ["0.11.0", SCHEMA_VERSION])
                self.assertTrue(fabric.log.chain.verify(fabric.log.read()).ok)
            finally:
                fabric.close()

    def test_tampered_authentic_fixture_is_reported_as_unsound(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tampered.db"
            self._materialize_v011(path)
            connection = sqlite3.connect(path)
            try:
                connection.execute("DROP TRIGGER IF EXISTS events_no_update")
                seq, payload = connection.execute(
                    "SELECT seq, payload FROM events WHERE type = 'MemoryCreated' LIMIT 1"
                ).fetchone()
                event = json.loads(payload)
                event["memory"]["content"] = "modified after release"
                with connection:
                    connection.execute("UPDATE events SET payload = ? WHERE seq = ?",
                                       (json.dumps(event), seq))
            finally:
                connection.close()
            output = StringIO()
            with redirect_stdout(output):
                code = main(["--json", "--db", str(path), "doctor"])
            report = json.loads(output.getvalue())
            self.assertEqual(code, 5)
            chain = next(row for row in report["findings"] if row["name"] == "event chain")
            self.assertEqual(chain["status"], "fail")


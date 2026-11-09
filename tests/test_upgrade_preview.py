from __future__ import annotations

import contextlib
import hashlib
import io
import sqlite3
import tempfile
import unittest
from pathlib import Path

from memory_fabric import MemoryFabric
from memory_fabric.cli import main
from memory_fabric.upgrade_preview import preview_upgrade

ROOT = Path(__file__).resolve().parents[1]


class UpgradePreview(unittest.TestCase):
    def test_supported_store_preview_preserves_exact_database_bytes(self) -> None:
        (ROOT / ".task-tmp").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / ".task-tmp") as directory:
            database = Path(directory) / "store.db"
            fabric = MemoryFabric(database, seed=0)
            fabric.remember("agent", "retained fixture", scope="team")
            fabric.close()
            before = hashlib.sha256(database.read_bytes()).hexdigest()
            report = preview_upgrade(database)
            after = hashlib.sha256(database.read_bytes()).hexdigest()
            self.assertTrue(report["store_byte_identical"])
            self.assertTrue(report["compatible_for_current_reader"])
            self.assertEqual(report["sha256_before"], before)
            self.assertEqual(report["sha256_after"], after)
            self.assertEqual(report["event_count"], 2)

    def test_incompatible_and_malformed_versions_are_enumerated_read_only(self) -> None:
        (ROOT / ".task-tmp").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / ".task-tmp") as directory:
            database = Path(directory) / "future.db"
            connection = sqlite3.connect(database)
            try:
                connection.execute("CREATE TABLE events (seq INTEGER, event_id TEXT, schema_version TEXT, payload TEXT)")
                connection.execute("INSERT INTO events VALUES (1, 'a', '9.0.0', '{}')")
                connection.execute("INSERT INTO events VALUES (2, 'b', 'bad', '{}')")
                connection.commit()
            finally:
                connection.close()
            before = database.read_bytes()
            report = preview_upgrade(database)
            self.assertFalse(report["compatible_for_current_reader"])
            codes = {item["code"] for item in report["incompatibilities"]}
            self.assertIn("unsupported_schema_version", codes)
            self.assertIn("malformed_schema_version", codes)
            self.assertEqual(database.read_bytes(), before)

    def test_cli_uses_global_database_and_exits_nonzero_for_incompatibility(self) -> None:
        (ROOT / ".task-tmp").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / ".task-tmp") as directory:
            database = Path(directory) / "future.db"
            connection = sqlite3.connect(database)
            try:
                connection.execute("CREATE TABLE events (seq INTEGER, event_id TEXT, schema_version TEXT, payload TEXT)")
                connection.execute("INSERT INTO events VALUES (1, 'a', '9.0.0', '{}')")
                connection.commit()
            finally:
                connection.close()
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = main(["--db", str(database), "upgrade-preview"])
            self.assertEqual(code, 5)
            self.assertIn("unsupported_schema_version", output.getvalue())


if __name__ == "__main__":
    unittest.main()

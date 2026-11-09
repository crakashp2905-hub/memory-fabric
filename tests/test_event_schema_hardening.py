from __future__ import annotations

import json
import shutil
import sqlite3
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from memory_fabric import MemoryFabric
from memory_fabric.events import Event


class EventSchemaHardening(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "store.db"

    def test_unknown_additive_memory_field_replays(self) -> None:
        fabric = MemoryFabric(self.path, auto_activate=True, encrypt_content=False)
        mid = fabric.remember("writer", "Valve seven is open.")
        fabric.close()
        connection = sqlite3.connect(self.path)
        try:
            with connection:
                connection.execute("DROP TRIGGER events_no_update")
                connection.execute("DROP TRIGGER integrity_chain_no_delete")
                connection.execute("DELETE FROM integrity_chain")
                seq, raw = connection.execute(
                    "SELECT seq, payload FROM events WHERE type = 'MemoryCreated'"
                ).fetchone()
                payload = json.loads(raw)
                payload["memory"]["future_optional_field"] = {"ignored": True}
                connection.execute(
                    "UPDATE events SET payload = ? WHERE seq = ?",
                    (json.dumps(payload), seq),
                )
        finally:
            connection.close()
        reopened = MemoryFabric(self.path)
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.get(mid).content, "Valve seven is open.")

    def test_duplicate_event_id_is_rejected_atomically(self) -> None:
        fabric = MemoryFabric(self.path)
        self.addCleanup(fabric.close)
        original = Event(type="FutureAdditiveEvent", ts=1, payload={"x": 1})
        fabric.log.append(original)
        head = fabric.log.head_seq
        with self.assertRaises(sqlite3.IntegrityError):
            fabric.log.append(replace(original, payload={"x": 2}))
        self.assertEqual(fabric.log.head_seq, head)

    def test_missing_or_malformed_version_is_refused_before_write(self) -> None:
        fabric = MemoryFabric(self.path)
        self.addCleanup(fabric.close)
        head = fabric.log.head_seq
        for value in (None, "", "1", "latest", "1.2"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                fabric.log.append(Event(type="Unknown", ts=1, schema_version=value))  # type: ignore[arg-type]
        self.assertEqual(fabric.log.head_seq, head)

    def test_malformed_persisted_version_refuses_replay(self) -> None:
        fabric = MemoryFabric(self.path, encrypt_content=False)
        fabric.remember("writer", "Valve seven is open.")
        fabric.close()
        connection = sqlite3.connect(self.path)
        try:
            with connection:
                connection.execute("DROP TRIGGER events_no_update")
                connection.execute("UPDATE events SET schema_version = '' WHERE seq = 1")
        finally:
            connection.close()
        with self.assertRaisesRegex(ValueError, "schema_version"):
            MemoryFabric(self.path)

    def test_backup_rollback_restores_readable_pre_upgrade_state(self) -> None:
        fabric = MemoryFabric(self.path, auto_activate=True, encrypt_content=False)
        mid = fabric.remember("writer", "Valve seven is open.")
        fabric.close()
        backup = self.path.with_name("pre-upgrade.db")
        shutil.copy2(self.path, backup)

        connection = sqlite3.connect(self.path)
        try:
            with connection:
                connection.execute("DROP TRIGGER events_no_update")
                connection.execute("UPDATE events SET schema_version = '99.0.0'")
        finally:
            connection.close()
        # Newer but well-formed events can be inspected, while `doctor` is the
        # supported action gate that refuses the partial projection.
        from io import StringIO
        from unittest.mock import patch
        from memory_fabric.cli import main

        with patch("sys.stdout", StringIO()):
            self.assertEqual(main(["--json", "--db", str(self.path), "doctor"]), 5)

        self.path.unlink()
        shutil.copy2(backup, self.path)
        rolled_back = MemoryFabric(self.path)
        self.addCleanup(rolled_back.close)
        self.assertEqual(rolled_back.get(mid).content, "Valve seven is open.")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

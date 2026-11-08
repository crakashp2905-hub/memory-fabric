from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from memory_fabric import MemoryFabric
from memory_fabric.eventlog import EventLog


class StorageFailureModes(unittest.TestCase):
    def test_malformed_path_fails_with_actionable_os_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parent_file = Path(tmp) / "not-a-directory"
            parent_file.write_text("x", encoding="utf-8")
            with self.assertRaises((OSError, sqlite3.OperationalError)):
                EventLog(parent_file / "store.db")

    def test_readonly_database_refuses_write_without_partial_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "store.db"
            seed = EventLog(path)
            from memory_fabric.events import Event
            seed.append(Event(type="Seed", ts=1, payload={"ok": True}))
            seed.close()

            readonly = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
            try:
                before = readonly.execute("SELECT MAX(seq) FROM events").fetchone()[0]
                with self.assertRaises(sqlite3.OperationalError):
                    readonly.execute(
                        "INSERT INTO events (event_id, ts, type, agent_id, episode_id, "
                        "schema_version, payload) VALUES ('test-id', 2, 'MustFail', '', '', '1.0', '{}')"
                    )
                self.assertEqual(readonly.execute("SELECT MAX(seq) FROM events").fetchone()[0], before)
                self.assertEqual(readonly.execute("SELECT type FROM events").fetchall(), [("Seed",)])
            finally:
                readonly.close()

    def test_database_full_error_rolls_back_projection_and_event_log(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "store.db"
            fabric = MemoryFabric(path, auto_activate=True)
            try:
                prior = fabric.remember("agent_a", "short value")
                before_head = fabric.log.head_seq
                # A tiny page limit provides a deterministic SQLITE_FULL fault
                # during the append transaction, without filling the host disk.
                fabric.log._conn.execute("PRAGMA max_page_count=2")
                payload = "x" * 200_000
                with self.assertRaises(sqlite3.OperationalError) as caught:
                    fabric.remember("agent_a", payload)
                self.assertIn("full", str(caught.exception).lower())
                self.assertEqual(fabric.log.head_seq, before_head)
                self.assertEqual(set(fabric.state.memories), {prior})
                reopened = MemoryFabric(path)
                try:
                    self.assertEqual(set(reopened.state.memories), {prior})
                    self.assertEqual(reopened.log.head_seq, before_head)
                finally:
                    reopened.close()
            finally:
                fabric.close()


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from memory_fabric import MemoryFabric
from memory_fabric.governance import cipher


class FailSafeEnvironment(unittest.TestCase):
    def test_sqlite_full_refuses_write_without_partial_projection(self) -> None:
        # SQLite's page limit: a file store, which stays on SQLite in every run.
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        fabric = MemoryFabric(Path(scratch.name) / "store.db", seed=0, encrypt_content=False)
        try:
            before_events = len(fabric.log)
            before_memories = len(fabric.state.memories)
            connection = fabric.log._conn
            pages = int(connection.execute("PRAGMA page_count").fetchone()[0])
            connection.execute(f"PRAGMA max_page_count={pages}")
            with self.assertRaisesRegex(sqlite3.OperationalError, "disk is full"):
                fabric.remember("agent", "X" * 100_000, scope="team")
            self.assertEqual(len(fabric.log), before_events)
            self.assertEqual(len(fabric.state.memories), before_memories)
        finally:
            fabric.close()

    def test_missing_optional_crypto_uses_authenticated_zero_dependency_suite(self) -> None:
        with patch.object(cipher, "profile", return_value="compatible"), \
             patch.object(cipher, "aead_available", return_value=False):
            suite = cipher.default_suite()
        self.assertIsInstance(suite, cipher.EncryptThenMac)
        envelope = suite.seal(b"offline content", bytes(range(32)), b"fixture")
        self.assertEqual(suite.unseal(envelope, bytes(range(32)), b"fixture"),
                         b"offline content")

    def test_production_crypto_profile_fails_closed_when_optional_library_missing(self) -> None:
        with patch.object(cipher, "profile", return_value="production"), \
             patch.object(cipher, "aead_status", return_value=(False, "not installed")):
            with self.assertRaisesRegex(cipher.IntegrityError, "production cryptography profile"):
                cipher.default_suite()


if __name__ == "__main__":
    unittest.main()

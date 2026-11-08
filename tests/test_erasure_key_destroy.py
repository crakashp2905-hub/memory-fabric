import sqlite3
import unittest
from tempfile import TemporaryDirectory
from pathlib import Path

from memory_fabric.governance.erasure import CallbackKeyProvider, ContentVault


class TestExternalKeyErasure(unittest.TestCase):
    def test_content_vault_destroys_external_key_material(self) -> None:
        with TemporaryDirectory() as directory:
            connection = sqlite3.connect(Path(directory) / "store.db")
            connection.row_factory = sqlite3.Row
            held: dict[str, bytes] = {}

            def destroy(memory_id: str) -> bool:
                return held.pop(memory_id, None) is not None

            provider = CallbackKeyProvider(
                fetch=held.get,
                create=lambda memory_id: held.setdefault(memory_id, b"K" * 32),
                destroy=destroy,
            )
            try:
                vault = ContentVault(connection, keys=provider, now_ms=lambda: 10)
                vault.key_for("memory1", 10000)
                self.assertIn("memory1", held)

                with connection:
                    self.assertTrue(vault.erase("memory1", "subject request", 20000))

                self.assertNotIn("memory1", held)
                self.assertTrue(vault.status("memory1").erased)
            finally:
                connection.close()

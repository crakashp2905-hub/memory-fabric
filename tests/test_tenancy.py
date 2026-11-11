"""Physical tenant isolation: separate files, separate keys, nothing shared."""

from __future__ import annotations

import contextlib
import io
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from memory_fabric import MemoryFabric
from memory_fabric.governance.erasure import DirectoryKeyProvider
from memory_fabric.tenancy import TenantRouter


class Router(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(self.enterContext(TemporaryDirectory()))
        self.router = TenantRouter(self.root, auto_activate=True)
        self.addCleanup(self.router.close)

    def test_each_tenant_has_its_own_file_and_keys(self) -> None:
        a = self.router.view("acme", "ann").remember("Acme plans to acquire Contoso.", scope="team")
        b = self.router.view("globex", "gus").remember("Globex ships valves.", scope="team")
        self.assertEqual(self.router.tenants(), ["acme", "globex"])
        self.assertNotIn(a, self.router.store("globex").state.memories)
        self.assertEqual(self.router.view("globex", "gus").retrieve("acquire Contoso").exposed, [])
        self.assertNotEqual(self.router.store("acme").store_id, self.router.store("globex").store_id)
        db_a, db_b = self.root / "acme" / "store.db", self.root / "globex" / "store.db"
        keys_a, keys_b = self.root / "acme" / "keys", self.root / "globex" / "keys"
        self.assertNotEqual(db_a.resolve(), db_b.resolve())
        self.assertNotEqual(keys_a.resolve(), keys_b.resolve())
        key_a = DirectoryKeyProvider(keys_a).get(a)
        key_b = DirectoryKeyProvider(keys_b).get(b)
        self.assertIsNotNone(key_a)
        self.assertIsNotNone(key_b)
        self.assertNotEqual(key_a, key_b)

        # Backups are explicitly tenant-addressed and carry separate key files.
        self.router.close()
        backup_a, backup_b = self.root / "backups" / "acme.bak", self.root / "backups" / "globex.bak"
        backup_a.parent.mkdir()
        from memory_fabric.cli import main

        for tenant, database, key_dir, backup in (
                ("acme", db_a, keys_a, backup_a), ("globex", db_b, keys_b, backup_b)):
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                result = main(["--db", str(database), "--keys", str(key_dir), "backup",
                               str(backup), "--with-keys"])
            self.assertEqual(result, 0, tenant)
        self.assertNotEqual(backup_a.resolve(), backup_b.resolve())
        manifest_a = json.loads(backup_a.with_name(backup_a.name + ".manifest.json").read_text())
        manifest_b = json.loads(backup_b.with_name(backup_b.name + ".manifest.json").read_text())
        self.assertIn("acme.bak.keys", " ".join(manifest_a["files"]))
        self.assertIn("globex.bak.keys", " ".join(manifest_b["files"]))

    def test_another_tenants_keys_cannot_read_the_file(self) -> None:
        self.router.view("acme", "ann").remember("Acme plans to acquire Contoso.", scope="team")
        self.router.view("globex", "gus").remember("x", scope="team")
        self.router.close()
        try:
            wrong = MemoryFabric(str(self.root / "acme" / "store.db"),
                                 key_provider=DirectoryKeyProvider(str(self.root / "globex" / "keys")))
        except Exception:  # noqa: BLE001 - refusing to open is the strongest outcome
            return
        try:
            readable = [m.content for m in wrong.state.memories.values()]
        finally:
            wrong.close()
        self.assertFalse(any("Contoso" in c for c in readable), readable)

    def test_tenant_ids_cannot_name_a_path(self) -> None:
        for bad in ("../acme", "Acme", "a/b", "", "a" * 65, "..", "acme x",
                    "acme\n", None, 7):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.router.store(bad)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

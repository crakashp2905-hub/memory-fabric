"""A current erasure ledger prevents an old backup restoring usable content."""
from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from memory_fabric import MemoryFabric
from memory_fabric.cli import main
from memory_fabric.governance.erasure import ERASED_MARKER


class TestRestoreErasureReconciliation(unittest.TestCase):
    def test_erasure_after_backup_is_applied_before_restore_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.db"
            fabric = MemoryFabric(str(source))
            memory_id = fabric.remember("agent", "sensitive actionable instruction")
            fabric.validate(memory_id, actor="reviewer")
            fabric.close()

            backup = root / "old.db"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["--db", str(source), "backup", str(backup)]), 0)

            fabric = MemoryFabric(str(source))
            fabric.erase_content(memory_id, "subject request", actor="privacy-officer")
            fabric.close()
            ledger = root / "current-erasure-ledger.json"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["--db", str(source), "export-erasure-ledger",
                                       str(ledger)]), 0)
            self.assertNotIn("sensitive", ledger.read_text(encoding="utf-8"))
            self.assertEqual(json.loads(ledger.read_text(encoding="utf-8"))["erasures"],
                             [{"memory_id": memory_id}])

            dest = root / "restored"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["restore", str(backup), str(dest),
                                       "--erasure-ledger", str(ledger)]), 0)
            restored = MemoryFabric(str(dest / "store.db"))
            try:
                self.assertEqual(restored.get(memory_id).content, ERASED_MARKER)
                events = list(restored.log.read())
                self.assertEqual(sum(event.type == "ContentErased" for event in events), 1)
                self.assertEqual(events[-1].payload["memory_id"], memory_id)
                self.assertEqual(events[-1].agent_id, "restore-erasure-ledger")
                self.assertTrue(restored.log.chain.verify(events).ok)
            finally:
                restored.close()

    def test_restore_without_current_ledger_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.db"
            fabric = MemoryFabric(str(source))
            fabric.remember("agent", "some memory")
            fabric.close()
            backup = root / "old.db"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["--db", str(source), "backup", str(backup)]), 0)
                with self.assertRaises(SystemExit) as raised:
                    main(["restore", str(backup), str(root / "restored")])
                self.assertEqual(raised.exception.code, 2)
            self.assertFalse((root / "restored").exists())


if __name__ == "__main__":
    unittest.main()

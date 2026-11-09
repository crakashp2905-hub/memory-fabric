"""The operator backup/restore path retains each recovery checkpoint."""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestBackupRunbook(unittest.TestCase):
    def test_restore_checkpoints_follow_backup_and_erasure_reconciliation(self):
        text = (ROOT / "docs/RUNBOOKS.md").read_text(encoding="utf-8")
        start = text.index("## 8. Restoring from a backup")
        section = text[start:]
        stages = ["backup /backups/store.bak", "export-erasure-ledger",
                  "restore /backups/store.bak", " doctor",
                  "latest off-host checkpoint", "maintain --once"]
        offsets = [section.index(stage) for stage in stages]
        self.assertEqual(offsets, sorted(offsets))
        self.assertIn("manifest", section.lower())
        self.assertIn("tests/test_backup_custody.py", section)


if __name__ == "__main__":
    unittest.main()

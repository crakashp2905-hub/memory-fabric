"""Per-task source snapshot and explicit artifact commitments."""

from __future__ import annotations

import unittest
import re

from tools.cdm_task_inventory import OUTPUT, build_inventory


class TestTaskEvidenceInventory(unittest.TestCase):
    def test_every_task_binds_the_same_exact_source_snapshot(self):
        inventory = build_inventory()
        self.assertEqual(build_inventory(), inventory)
        self.assertEqual(inventory["task_count"], 240)
        self.assertRegex(inventory["git_head"], r"^[0-9a-f]{40,64}$")
        self.assertRegex(inventory["source_tree_sha256"], r"^[0-9a-f]{64}$")
        for task in inventory["tasks"]:
            with self.subTest(task=task["task_id"]):
                self.assertEqual(task["source_snapshot"]["git_head"], inventory["git_head"])
                self.assertEqual(task["source_snapshot"]["source_tree_sha256"],
                                 inventory["source_tree_sha256"])
                self.assertIs(type(task["source_snapshot"]["working_tree_dirty"]), bool)

    def test_artifacts_have_file_hash_and_last_revision_and_skip_self_hash(self):
        inventory = build_inventory()
        output = OUTPUT.relative_to(OUTPUT.parents[3]).as_posix()
        for task in inventory["tasks"]:
            for artifact in task["referenced_artifacts"]:
                self.assertRegex(artifact["sha256"], r"^[0-9a-f]{64}$")
                revision = artifact["last_committed_revision"]
                self.assertTrue(revision is None or re.fullmatch(r"[0-9a-f]{40,64}", revision))
                self.assertNotEqual(artifact["path"], output)


if __name__ == "__main__":
    unittest.main()

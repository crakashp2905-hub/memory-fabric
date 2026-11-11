from __future__ import annotations

import unittest
from pathlib import Path

from memory_fabric.causal_replay.tempfiles import allowed_root, temporary_workspace, validate_parent
from memory_fabric.causal_replay.types import CDMError


class TemporaryWorkspaceTests(unittest.TestCase):
    def test_rejects_parent_outside_approved_root(self) -> None:
        outside = allowed_root().parent / "outside-cdm-test-path"
        with self.assertRaisesRegex(CDMError, "outside the approved"):
            validate_parent(outside)

    def test_accepts_nested_parent_and_cleans_workspace(self) -> None:
        nested_parent = allowed_root() / "tempfile-policy-tests"
        nested_parent.mkdir(parents=True, exist_ok=True)
        workspace_path: Path
        with temporary_workspace(nested_parent) as workspace:
            workspace_path = workspace
            self.assertTrue(workspace.is_relative_to(allowed_root().resolve()))
            self.assertTrue(workspace.is_dir())
        self.assertFalse(workspace_path.exists())

if __name__ == "__main__":
    unittest.main()

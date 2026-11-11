"""The offline qualification gate keeps missing evidence explicit."""

from __future__ import annotations

import unittest

from tools.agent_outcome_gate import MANIFEST_PATH, overall_status, read_manifest


class TestAgentOutcomeGate(unittest.TestCase):
    def test_manifest_is_versioned_and_content_addressed(self) -> None:
        manifest, digest = read_manifest(MANIFEST_PATH)
        self.assertEqual(manifest["manifest_version"], 22)
        self.assertEqual(manifest["schema_id"], "memory-fabric.agent-outcome-gate.v22")
        self.assertEqual(len(digest), 64)
        self.assertIn("full_repository", [item["id"] for item in manifest["checks"]])

    def test_not_run_never_aggregates_to_qualification(self) -> None:
        checks = [
            {"required_for_scripted_qualification": True, "status": "PASS"},
            {"required_for_scripted_qualification": True, "status": "NOT_RUN"},
        ]
        self.assertEqual(overall_status(checks), "NOT_RUN")

    def test_required_failure_dominates_unrun_checks(self) -> None:
        checks = [
            {"required_for_scripted_qualification": True, "status": "NOT_RUN"},
            {"required_for_scripted_qualification": True, "status": "FAIL"},
        ]
        self.assertEqual(overall_status(checks), "FAIL")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

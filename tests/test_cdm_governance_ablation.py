"""Governance capture ablation detects stale access and metadata exposure."""

from __future__ import annotations

import unittest

from benchmarks.cdm_governance_ablation import run


class GovernanceAblationTests(unittest.TestCase):
    def test_current_policy_blocks_stale_reuse_without_false_block(self):
        result = run()
        self.assertEqual(result["metrics"], {
            "valid_case_false_blocks": 0,
            "governed_unauthorized_accepts": 0,
            "weak_stale_evidence_accepts": 2,
            "weak_unauthorized_accepts": 3,
            "governed_unauthorized_metadata_exposures": 0,
            "weak_unauthorized_metadata_exposures": 3})
        self.assertEqual(result["safety"], {"network_calls": 0, "tool_calls": 0,
            "authority_changes": 0, "plaintext_reported": False})
        self.assertTrue(all("memory_id" not in row and "content" not in row
                            for row in result["cases"]))


if __name__ == "__main__":
    unittest.main()

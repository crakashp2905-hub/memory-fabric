from __future__ import annotations

import unittest

from experiments.n6_06_utcp_policy_check import evaluate


class UtcpPolicyCheckTests(unittest.TestCase):
    def test_all_malicious_manuals_are_rejected_before_any_io(self) -> None:
        report = evaluate()
        self.assertTrue(report["acceptance_passed"])
        self.assertEqual(report["rejected_count"], report["corpus"]["cases"])
        self.assertEqual(report["accepted_safe_manual_tools"], ["lookup"])
        self.assertFalse(report["io_guards"]["triggered"])

    def test_version_and_transport_attack_cases_are_in_the_frozen_corpus(self) -> None:
        case_ids = {row["case_id"] for row in evaluate()["rejected"]}
        self.assertIn("future-utcp-version", case_ids)
        self.assertIn("unsupported-manual-version", case_ids)
        self.assertIn("cloud-metadata-host", case_ids)
        self.assertIn("file-transport", case_ids)
        self.assertIn("encoded-shell-command-substitution", case_ids)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest

from experiments.n5_09_partition_freshness import build_report


class PartitionFreshnessExperimentTests(unittest.TestCase):
    def test_reconnection_before_and_after_expiry_exposes_tradeoffs(self) -> None:
        report = build_report()
        early, late, offline, healthy = report["scenarios"]
        self.assertEqual(early["stale_knowledge_window_ms"], 2_000)
        self.assertEqual(early["stale_strict_action_window_ms"], 2_000)
        self.assertTrue(early["reconnected_and_retracted"])
        self.assertEqual(late["stale_knowledge_window_ms"], 6_000)
        self.assertEqual(late["stale_strict_action_window_ms"], 3_000)
        self.assertEqual(late["stale_strict_action_samples"], 3)
        self.assertTrue(late["reconnected_and_retracted"])
        self.assertEqual(offline["stale_knowledge_window_ms"], 6_000)
        self.assertEqual(offline["stale_read_samples"], 7)
        self.assertFalse(offline["reconnected_and_retracted"])
        self.assertGreater(healthy["strict_denied_while_origin_current_samples"], 0)

    def test_report_does_not_claim_zero_stale_knowledge_offline(self) -> None:
        report = build_report()
        self.assertEqual(report["evidence_class"], "DETERMINISTIC_CONTRACT_SIMULATION")
        self.assertIn("nonzero", report["conclusion"])
        self.assertIn("not a claim", report["conclusion"])


if __name__ == "__main__":
    unittest.main()

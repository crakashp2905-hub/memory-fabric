from __future__ import annotations

import unittest

from experiments.n5_08_minority_origin import COPY_COUNTS, run_case


class MinorityOriginResilienceTests(unittest.TestCase):
    def test_uncommon_correct_root_survives_many_correlated_wrong_copies(self) -> None:
        for copy_count in COPY_COUNTS:
            with self.subTest(correlated_wrong_copies=copy_count):
                row = run_case(copy_count)
                self.assertEqual(row["wrong_source_roots"], 1)
                self.assertEqual(row["wrong_support_independent_sources"], 1)
                self.assertTrue(row["wrong_support_artificial"])
                self.assertEqual(row["correct_source_roots"], 1)
                self.assertTrue(row["correct_alternative_retrieved"])
                self.assertEqual(row["distinct_source_roots_retrieved"], 2)

    def test_no_majority_winner_is_selected_when_independent_support_ties(self) -> None:
        row = run_case(24)
        self.assertTrue(row["support_contested"])
        self.assertIsNone(row["support_leading"])
        self.assertFalse(row["hypothesis_resolved"])

    def test_correct_minority_alternative_is_flagged_for_validation(self) -> None:
        row = run_case(12)
        self.assertEqual(row["correct_lifecycle_state"], "contested")
        self.assertEqual(row["retrieval_evidence_validity"], "invalid")
        self.assertEqual(row["retrieval_decision_readiness"], "review")

    def test_rejects_zero_or_negative_copy_count(self) -> None:
        for count in (0, -1):
            with self.subTest(count=count), self.assertRaises(ValueError):
                run_case(count)


if __name__ == "__main__":
    unittest.main()

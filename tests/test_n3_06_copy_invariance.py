from __future__ import annotations

import unittest

from benchmarks.n3_06_copy_invariance import run


class TestN306CopyInvariance(unittest.TestCase):
    def test_unrelated_attribution_is_stable_as_copies_multiply(self) -> None:
        result = run()
        self.assertTrue(result["useful_credit_stable"])
        self.assertTrue(result["irrelevant_copy_credit_zero"])
        self.assertEqual(result["copy_counts"], [0, 1, 2, 4, 8])
        for row in result["worlds"]:
            self.assertEqual(row["recognized_copy_count"], row["irrelevant_copy_count"])
            self.assertEqual(row["useful_exact_average_inclusion_effect"], 1.0)
            self.assertAlmostEqual(row["useful_exact_shapley"], 1.0)
            self.assertAlmostEqual(row["useful_ips_estimate"], 1.0)
            self.assertAlmostEqual(row["irrelevant_group_exact_shapley_total"], 0.0)
            self.assertAlmostEqual(row["irrelevant_group_ips_total"], 0.0)


if __name__ == "__main__":
    unittest.main()

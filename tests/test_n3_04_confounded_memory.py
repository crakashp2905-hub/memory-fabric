from __future__ import annotations

import unittest

from benchmarks.n3_04_confounded_memory import run


class TestN304ConfoundedMemory(unittest.TestCase):
    def test_ips_exposes_confounding_without_erasing_real_memory_effect(self) -> None:
        result = run()
        self.assertTrue(result["selection_enrichment_requirement_passed"])
        self.assertTrue(result["naive_bias_requirement_passed"])
        self.assertTrue(result["ips_recovery_requirement_passed"])
        self.assertAlmostEqual(result["true_average_treatment_effect"], 0.15)
        self.assertGreater(result["exposed_easy_rate"], result["exposed_hard_rate"])
        self.assertLessEqual(result["ips_absolute_error"], 0.04)
        self.assertGreaterEqual(result["naive_bias"], 0.20)
        self.assertTrue(result["ips_contrastive"])

    def test_seeded_confounding_fixture_is_reproducible(self) -> None:
        self.assertEqual(run(), run())


if __name__ == "__main__":
    unittest.main()

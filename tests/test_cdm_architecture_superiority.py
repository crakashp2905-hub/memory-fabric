import unittest

from benchmarks.cdm_architecture_superiority import (
    CONFIRMATORY_SEEDS,
    DEVELOPMENT_SEEDS,
    run,
)


class ArchitectureSuperiorityTests(unittest.TestCase):
    def test_development_preflight_uses_registered_seeds_and_oracle_ceiling(self):
        result = run(DEVELOPMENT_SEEDS, split="development")
        self.assertEqual(result["seeds"], DEVELOPMENT_SEEDS)
        self.assertEqual(result["primary"]["oracle_exceedances"], 0)
        self.assertTrue(all(row["removal_budget"] == 1 for row in result["rows"]))
        self.assertEqual(len(result["rows"]), len(DEVELOPMENT_SEEDS) * 6)
        self.assertEqual(result["safety"]["hidden_truth_visible_to_selectors"], False)

    def test_confirmatory_seed_list_is_fixed_and_disjoint(self):
        self.assertEqual(len(CONFIRMATORY_SEEDS), 20)
        self.assertFalse(set(DEVELOPMENT_SEEDS) & set(CONFIRMATORY_SEEDS))
        with self.assertRaises(ValueError):
            run((1, 2, 3, 4, 5), split="confirmatory")


if __name__ == "__main__":
    unittest.main()

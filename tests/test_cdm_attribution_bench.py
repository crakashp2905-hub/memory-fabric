import unittest

from benchmarks.cdm_attribution_bench import run


class AttributionBenchmarkTests(unittest.TestCase):
    def test_matched_arms_share_seeds_and_keep_negative_results(self):
        result = run((501, 502))
        expected = {"leave_one_out", "exact_subset_oracle", "exact_shapley",
            "sampled_shapley", "random", "recency", "car_full_suffix"}
        self.assertEqual(set(result["arms"]), expected)
        rows = [row for row in result["rows"] if row["arm"] in expected]
        self.assertEqual(len(rows), 2 * len(expected))
        for seed in (501, 502):
            self.assertEqual({row["seed"] for row in rows if row["seed"] == seed}, {seed})
            self.assertTrue(all(row["complete"] for row in rows if row["seed"] == seed))
        self.assertTrue(all(row["truth_hidden_until_proposal"] for row in rows))
        self.assertTrue(all(row["model_calls"] == row["api_tokens"] ==
                            row["external_charges"] == 0 for row in rows))
        self.assertTrue(all(row["removal_budget"] == 1
                            and row["network_calls"] == row["tool_calls"]
                            == row["authority_changes"] == 0 for row in rows))
        self.assertTrue(result["comparison_contract"]["same_seeded_worlds"])
        self.assertTrue(result["comparison_contract"]["same_one_removal_budget"])
        self.assertEqual(result["comparison_contract"]["cost_basis"],
            "measured local selector plus arm replay CPU/wall; peak is max phase usage")
        points = result["cost_quality_points"]
        self.assertEqual({point["arm"] for point in points}, expected)
        frontier = result["pareto_frontier"]
        self.assertTrue(frontier)
        self.assertTrue(all(point in points for point in frontier))


if __name__ == "__main__":
    unittest.main()

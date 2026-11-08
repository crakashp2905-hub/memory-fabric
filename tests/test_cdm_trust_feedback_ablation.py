import unittest

from benchmarks.cdm_trust_feedback_ablation import Experience, run, update_experience


class TrustFeedbackAblationTests(unittest.TestCase):
    def test_factorial_metrics_are_separate_and_reproducible(self):
        result = run((11, 12, 13, 14, 15), (21, 22, 23, 24, 25))
        self.assertEqual(len(result["rows"]), 4 * 3 * 5)
        self.assertEqual(result["safety"], {"authority_changes": 0, "network_calls": 0,
            "model_calls": 0, "tool_calls": 0, "truth_visible_to_proposer": False})
        self.assertFalse(result["oracle_exceeded"])
        for arm in result["arms"]:
            for scenario in result["scenarios"]:
                metric = result["metrics"][f"{arm}:{scenario}"]
                self.assertEqual(metric["n"], 5)
                self.assertGreaterEqual(metric["correct_memories_withheld"], 0)
                self.assertLessEqual(metric["correct_memory_withholding_rate"], 1)
                interval = metric["accuracy_normal_approx_95_interval"]
                self.assertLessEqual(0.0, interval[0])
                self.assertLessEqual(interval[1], 1.0)
            self.assertIn(f"{arm}:robustness:annotation_inversion", result["metrics"])
            self.assertIn(f"{arm}:robustness:feedback_inversion", result["metrics"])
        self.assertEqual(result, run((11, 12, 13, 14, 15), (21, 22, 23, 24, 25)))

    def test_feedback_update_is_bounded_and_missing_feedback_is_noop(self):
        state = Experience()
        self.assertEqual(update_experience(state, None), state)
        self.assertEqual(update_experience(state, 1.0), Experience(0.55, 1))
        self.assertEqual(update_experience(Experience(0.7, 20), 0.0), Experience(0.7, 20))
        with self.assertRaises(ValueError):
            update_experience(state, 1.1)

    def test_seed_splits_must_be_disjoint(self):
        with self.assertRaises(ValueError):
            run((1, 2, 3, 4, 5), (5, 6, 7, 8, 9))


if __name__ == "__main__":
    unittest.main()

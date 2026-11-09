import unittest

from benchmarks.cdm_tame_inspired import Experience, run, update_experience


class TameInspiredTests(unittest.TestCase):
    def test_bounded_ema_and_missing_feedback(self):
        state = Experience()
        self.assertEqual(update_experience(state, None), state)
        updated = update_experience(state, 1.0)
        self.assertEqual(updated, Experience(0.55, 1))
        capped = update_experience(Experience(0.7, 20), 0.0)
        self.assertEqual(capped, Experience(0.7, 20))

    def test_invalid_reward_rejected(self):
        with self.assertRaises(ValueError):
            update_experience(Experience(), 1.1)

    def test_prequential_protocol_is_reproducible_and_disjoint(self):
        result = run((1, 2), (3, 4))
        self.assertEqual(result["safety"], {"authority_changes": 0,
                                           "network_calls": 0, "tool_calls": 0})
        self.assertEqual(result["train_final_annotations"],
                         run((1, 2), (3, 4))["train_final_annotations"])
        self.assertIn("heldout_prequential:tame_inspired", result["summary"])
        self.assertEqual(result["paired_summary"]["heldout_prequential:tame_inspired-minus-factual"]["n"], 2)
        self.assertIn("tame_annotation_score_before", result["rows"][0])
        self.assertTrue(all(row["outcome_revealed_after_proposal"] for row in result["rows"]))
        with self.assertRaises(ValueError):
            run((1, 2), (2, 3))


if __name__ == "__main__":
    unittest.main()

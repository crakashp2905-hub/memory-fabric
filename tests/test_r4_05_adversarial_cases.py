from __future__ import annotations

import unittest

from experiments.r4_05_adversarial_cases import (
    DISTRACTOR_SEED, IDENTIFIER_SEED, N_CASES, TASK_SEED, build_cases, shortcut_results,
)


class R405AdversarialCases(unittest.TestCase):
    def test_independent_streams_and_cases_are_reproducible(self) -> None:
        self.assertEqual(len({TASK_SEED, DISTRACTOR_SEED, IDENTIFIER_SEED}), 3)
        self.assertEqual(build_cases(), build_cases())
        self.assertEqual(len(build_cases()), N_CASES)

    def test_every_case_has_a_near_miss_and_irrelevant_distractors(self) -> None:
        for case in build_cases():
            rows = case["options"]
            self.assertEqual(len(rows), 4)
            matching_near_miss = [row for row in rows
                                  if row["entity"] == case["entity"]
                                  and row["attribute"] == case["attribute"]
                                  and row["version"] == "superseded"]
            self.assertEqual(len(matching_near_miss), 1)
            current = [row for row in rows if row["version"] == "current"
                       and row["entity"] == case["entity"]]
            self.assertEqual(len(current), 1)
            self.assertEqual(current[0]["value"], case["answer"])
            self.assertEqual(sum(row["entity"] != case["entity"] for row in rows), 2)

    def test_surface_and_identifier_shortcuts_do_not_pass(self) -> None:
        result = shortcut_results(build_cases())
        self.assertEqual(result["surface_template_count"], 1)
        self.assertLessEqual(result["first_position_shortcut"]["accuracy"], 0.35)
        self.assertLessEqual(result["lexicographic_identifier_shortcut"]["accuracy"], 0.35)
        self.assertEqual(sum(result["answer_position_counts"].values()), N_CASES)
        self.assertEqual(result["irrelevant_distractor_count"], 2 * N_CASES)


if __name__ == "__main__":
    unittest.main()

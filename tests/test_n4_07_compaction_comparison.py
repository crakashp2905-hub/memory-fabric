from __future__ import annotations

import unittest
from typing import Any, ClassVar

from experiments.n4_07_compaction_comparison import ARMS, evaluate_seed


class CompactionComparison(unittest.TestCase):
    result: ClassVar[dict[str, Any]]

    @classmethod
    def setUpClass(cls) -> None:
        cls.result = evaluate_seed(11)

    def test_all_registered_arms_run_on_same_eight_tasks(self) -> None:
        self.assertEqual(set(self.result["arms"]), set(ARMS))
        self.assertEqual(self.result["task_count"], 8)
        self.assertTrue(self.result["dependency_map_verified"])
        self.assertTrue(all(arm["task_count"] == 8 for arm in self.result["arms"].values()))

    def test_full_history_is_the_fixture_ceiling(self) -> None:
        baseline = self.result["arms"]["no_compaction"]
        self.assertEqual(baseline["task_success_rate"], 1.0)
        self.assertTrue(all(
            arm["task_success_rate"] <= baseline["task_success_rate"]
            for arm in self.result["arms"].values()
        ))

    def test_provenance_arm_resolves_world_time_without_stale_action(self) -> None:
        arm = self.result["arms"]["provenance_preserving_summary"]
        self.assertEqual(arm["task_success_rate"], 1.0)
        self.assertEqual(arm["false_stale_actions"], 0)
        self.assertEqual(arm["source_identity_reconstruction_fidelity"], 1.0)

    def test_extractive_text_has_no_source_identity_and_remains_byte_measured(self) -> None:
        arm = self.result["arms"]["extractive_summary"]
        self.assertGreater(arm["context_bytes_utf8"], 0)
        self.assertEqual(arm["source_identity_reconstruction_fidelity"], 0.0)
        self.assertEqual(arm["factual_text_reconstruction_fidelity"], 1.0)


if __name__ == "__main__":
    unittest.main()

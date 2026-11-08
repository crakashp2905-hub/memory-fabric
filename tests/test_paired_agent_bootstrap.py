from __future__ import annotations

import json
import unittest

from benchmarks.paired_agent_bootstrap import build_report, holm_adjust
from benchmarks.stats import paired_bootstrap


class PairedAgentBootstrap(unittest.TestCase):
    def test_registered_50_agent_cases_are_paired_and_clustered(self) -> None:
        with open("research/results/r3-02-matched-agent-arms.json", encoding="utf-8") as source_file:
            report = build_report(json.load(source_file))
        self.assertEqual(len(report["split_identity"]["task_cases"]), 24)
        self.assertEqual(report["inferential_status"], "EXPLORATORY_POST_OUTCOME_HIERARCHY_AMENDMENT")
        self.assertEqual(report["outcome_hierarchy"]["primary"], ["overall_task_success"])
        self.assertEqual(set(report["family_outcomes"]["memory_fabric"]),
                         {"supported", "corrected", "contested", "missing"})
        self.assertFalse(report["method"]["multiplicity"]["current_report_confirmatory"])
        self.assertEqual(set(report["method"]["multiplicity"]["adjusted_p_values"]),
                         {"isolated", "pooled_shared", "blanket_retraction"})
        self.assertEqual(report["method"]["resamples"], 20_000)
        self.assertIn("task cases are resampled as clusters",
                      report["method"]["correlation_assumption"])
        for comparison in report["comparisons"].values():
            self.assertEqual(comparison["sample_size_unique_task_cases"], 24)
            self.assertEqual(comparison["attempts_per_arm"], 1200)
            self.assertLessEqual(comparison["lo"], comparison["diff"])
            self.assertGreaterEqual(comparison["hi"], comparison["diff"])

    def test_pairing_preserves_clustered_difference(self) -> None:
        result = paired_bootstrap([0, 0, 1, 1], [1, 1, 1, 1], seed=4,
                                  clusters=["a", "a", "b", "b"], resamples=1000)
        self.assertEqual(result["diff"], 0.5)
        self.assertLessEqual(result["lo"], result["hi"])

    def test_holm_adjustment_is_monotonic_and_caps_at_one(self) -> None:
        self.assertEqual(holm_adjust({"a": 0.01, "b": 0.03, "c": 0.8}),
                         {"a": 0.03, "b": 0.06, "c": 0.8})
        self.assertEqual(holm_adjust({"x": 0.9, "y": 0.8}), {"y": 1.0, "x": 1.0})

    def test_holm_adjustment_rejects_invalid_p_values(self) -> None:
        with self.assertRaisesRegex(ValueError, "finite values"):
            holm_adjust({"bad": float("nan")})


if __name__ == "__main__":
    unittest.main()

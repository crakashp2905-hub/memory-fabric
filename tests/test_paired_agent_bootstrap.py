from __future__ import annotations

import json
import unittest

from benchmarks.paired_agent_bootstrap import build_report
from benchmarks.stats import paired_bootstrap


class PairedAgentBootstrap(unittest.TestCase):
    def test_registered_50_agent_cases_are_paired_and_clustered(self) -> None:
        with open("research/results/r3-02-matched-agent-arms.json", encoding="utf-8") as source_file:
            report = build_report(json.load(source_file))
        self.assertEqual(len(report["split_identity"]["task_cases"]), 24)
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


if __name__ == "__main__":
    unittest.main()

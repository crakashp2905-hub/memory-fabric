from __future__ import annotations

import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from n1_09_decision_continuity import run  # noqa: E402


class DecisionContinuityBenchmarkTests(unittest.TestCase):
    def test_exact_index_routes_all_and_only_decisions_relying_on_correction(self) -> None:
        result = run(decisions=200, seeds=[41, 42])
        for row in result["runs"]:
            expected = row["affected_decisions_oracle"]
            self.assertTrue(row["indexed_impacts_match_oracle"])
            self.assertEqual(row["correction_events_scanned"], 1)
            exact = row["arms"]["exact_dependency_index"]
            plain = row["arms"]["plain_versioning"]
            blanket = row["arms"]["blanket_invalidation"]
            self.assertEqual(exact["re_evaluations"], expected)
            self.assertEqual(exact["unnecessary_re_evaluations"], 0)
            self.assertEqual(exact["stale_decisions"], 0)
            self.assertEqual(exact["correctly_routed_decisions"], 200)
            self.assertEqual(plain["stale_decisions"], expected)
            self.assertEqual(blanket["re_evaluations"], 200)
            self.assertEqual(blanket["unnecessary_re_evaluations"], 200 - expected)
            self.assertEqual(blanket["stale_decisions"], 0)

    def test_seeded_dataset_and_counts_reproduce_without_timing_assumptions(self) -> None:
        first = run(decisions=100, seeds=[9001])
        second = run(decisions=100, seeds=[9001])
        self.assertEqual(first["runs"][0]["dataset_sha256"],
                         second["runs"][0]["dataset_sha256"])
        for arm in first["aggregate"]["arms"]:
            left = first["aggregate"]["arms"][arm]
            right = second["aggregate"]["arms"][arm]
            for key in ("re_evaluations", "unnecessary_re_evaluations", "stale_decisions",
                        "correctly_routed_decisions", "decision_correctness_rate_median"):
                self.assertEqual(left[key], right[key])


if __name__ == "__main__":
    unittest.main()

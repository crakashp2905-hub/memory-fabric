"""Known-bad arms must fail on the deterministic internal benchmark suites."""
from __future__ import annotations

import unittest

from benchmarks.enumeration import ARMS as ENUMERATION_ARMS, run_seed as run_enumeration
from benchmarks.memoryworld2 import run_seed as run_memoryworld2


class KnownFailureControls(unittest.TestCase):
    def test_int01_overwrite_baseline_fails_to_recover_changed_facts(self) -> None:
        scores = run_memoryworld2(1)
        self.assertLess(scores["valid:overwrite"], scores["valid:oracle"])
        self.assertEqual(scores["valid:valid_time"], scores["valid:oracle"])

    def test_int03_search_arms_fail_known_exact_enumeration_cases(self) -> None:
        scores = run_enumeration(1, ENUMERATION_ARMS)
        exact = {arm: sum(row["exact"] for row in result["rows"]) / len(result["rows"])
                 for arm, result in scores.items()}
        self.assertEqual(exact["oracle"], 1.0)
        self.assertLess(exact["typed"], exact["oracle"])
        self.assertLess(exact["nav"], exact["oracle"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

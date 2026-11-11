from __future__ import annotations

import unittest

from experiments.n6_07_code_mode_static_bounds import evaluate


class CodeModeStaticBoundsTests(unittest.TestCase):
    def test_hostile_programming_constructs_and_resource_overruns_fail_closed(self) -> None:
        report = evaluate()
        self.assertTrue(report["acceptance_passed"])
        self.assertEqual(report["corpus"]["cases"], report["corpus"]["rejected"])
        self.assertEqual(len(report["bounds"]["over_limit_rejections"]), 4)
        self.assertTrue(report["bounds"]["calls_at_limit_accepted"])
        self.assertFalse(report["grammar"]["optional_branching"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

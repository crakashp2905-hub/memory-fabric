from __future__ import annotations

import unittest

from tools.runbook_drill import DRILLS, run_drill, run_mass_retraction


class RunbookDrills(unittest.TestCase):
    def test_each_local_operational_drill_passes(self) -> None:
        for name in (*DRILLS, "mass-retraction"):
            with self.subTest(drill=name):
                self.assertTrue(run_drill(name)["passed"])

    def test_mass_retraction_reports_all_descendants(self) -> None:
        report = run_mass_retraction(descendants=25)
        self.assertEqual(report["descendants_contested"], 25)
        self.assertEqual(report["unrelated_effects"], 0)


if __name__ == "__main__":
    unittest.main()

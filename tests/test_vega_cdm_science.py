"""The Vega-CDM registration validator (VEGA S16)."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from benchmarks import vega_cdm_confirmatory as conf

ROOT = Path(__file__).resolve().parents[1]
DRAFT = json.loads((ROOT / "research" / "prereg" / "vega-cdm-v1.json").read_text())


def frozen(**changes):
    reg = copy.deepcopy(DRAFT)
    reg["development_evidence"]["unsafe_increase"] = 0
    reg["holdout"]["pairs"] = 200
    for path, value in changes.items():
        node = reg
        keys = path.split(".")
        for key in keys[:-1]:
            node = node[key]
        node[keys[-1]] = value
    reg["status"] = "FROZEN"
    reg["design_sha256"] = conf.design_digest(reg)
    return reg


class Registration(unittest.TestCase):
    def test_the_committed_draft_is_no_go_and_says_why(self):
        problems = conf.validate(DRAFT)
        self.assertEqual(conf.decide(problems), "NO_GO")
        self.assertTrue(any("safety gate" in p for p in problems))
        self.assertTrue(any("underpowered" in p for p in problems))

    def test_a_complete_powered_frozen_registration_validates(self):
        self.assertEqual(conf.validate(frozen()), [])

    def test_an_effect_above_the_oracle_headroom_is_impossible(self):
        problems = conf.validate(frozen(minimum_practical_gain=0.2))
        self.assertTrue(any("headroom" in p for p in problems))

    def test_overlapping_splits_and_edited_designs_are_refused(self):
        self.assertTrue(conf.validate(frozen(**{"holdout.seeds": [0, 100]})))
        reg = frozen()
        reg["minimum_practical_gain"] = 0.04
        self.assertIn("design digest does not match the registration", conf.validate(reg))

    def test_the_denominator_comparator_and_adjustment_are_fixed(self):
        for change in ({"denominator": "completed_cases"}, {"adjustment": "none"},
                       {"comparator.chosen_on": "confirmatory"}, {"exclusions": "post_hoc"}):
            with self.subTest(change=change):
                self.assertTrue(conf.validate(frozen(**change)))

    def test_zero_unsafe_events_give_a_bound_not_zero_risk(self):
        self.assertEqual(conf.unsafe_upper_bound(56), 0.0521)
        self.assertGreater(conf.unsafe_upper_bound(1000), 0)
        self.assertIsNone(conf.unsafe_upper_bound(0))


if __name__ == "__main__":
    unittest.main()

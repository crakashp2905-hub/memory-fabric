"""Feature-freeze release controls: threshold ladder, issue register and qualification records."""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

from benchmarks import freeze_ladder as ladder_mod

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))


class Ladder(unittest.TestCase):
    def setUp(self) -> None:
        self.ladder = ladder_mod.load()

    def test_the_committed_ladder_is_sealed_and_intact(self) -> None:
        self.assertEqual(ladder_mod.problems(self.ladder), [])
        self.assertTrue(self.ladder["digest"])

    def test_editing_a_threshold_after_sealing_is_detected(self) -> None:
        edited = copy.deepcopy(self.ladder)
        edited["metrics"]["vega_margin_over_shuffled_placebo"]["stages"]["S1_development_replication"][
            "threshold"] = 0.01
        self.assertTrue(any("edited after freezing" in p for p in ladder_mod.problems(edited)))
        self.assertEqual(ladder_mod.verdict("vega_margin_over_shuffled_placebo", "S1_development_replication",
                                            0.5, 500, passed_before=True, ladder=edited)["verdict"],
                         "INVALID_LADDER")

    def test_safety_bounds_never_relax_and_efficacy_margins_never_tighten(self) -> None:
        for name, metric in self.ladder["metrics"].items():
            values = [metric["stages"][s]["threshold"] for s in ladder_mod.STAGES]
            if metric["kind"] == "safety_upper_bound":
                self.assertEqual(values, sorted(values, reverse=True), name)
            else:
                self.assertEqual(values, sorted(values, reverse=True), name)
        loose = copy.deepcopy(self.ladder)
        stages = loose["metrics"]["vega_unsafe_omission_bound"]["stages"]
        stages["S3_confirmatory"]["threshold"] = 0.2
        loose["digest"] = ladder_mod.body_digest(loose)
        self.assertTrue(any("only tighten" in p for p in ladder_mod.problems(loose)))

    def test_a_gentler_stage_is_reachable_only_after_the_strict_one_and_only_on_new_rows(self) -> None:
        m = "vega_margin_over_shuffled_placebo"
        self.assertEqual(ladder_mod.verdict(m, "S1_development_replication", 0.01, 200, passed_before=False)
                         ["verdict"], "FAIL")
        self.assertEqual(ladder_mod.verdict(m, "S2_fresh_pilot", 0.06, 400, passed_before=False)["verdict"],
                         "NOT_ELIGIBLE")
        self.assertEqual(ladder_mod.verdict(m, "S2_fresh_pilot", 0.06, 400, passed_before=True,
                                            fresh_population=False)["verdict"], "NOT_ELIGIBLE")
        self.assertEqual(ladder_mod.verdict(m, "S2_fresh_pilot", 0.06, 100, passed_before=True)["verdict"],
                         "NOT_ELIGIBLE")
        self.assertEqual(ladder_mod.verdict(m, "S2_fresh_pilot", 0.06, 400, passed_before=True)["verdict"],
                         "PASS")


class Register(unittest.TestCase):
    def test_every_open_item_has_a_disposition_owner_and_closure(self) -> None:
        import freeze_register
        reg = freeze_register.build()
        self.assertEqual(freeze_register.check(reg), [])
        self.assertGreater(reg["open_items"], 0)
        ids = {i["id"] for i in reg["items"]}
        self.assertIn("gate:external_security_review", ids)  # nothing is silently dropped
        for item in reg["items"]:
            self.assertIn(item["disposition"], freeze_register.DISPOSITIONS)

    def test_the_committed_register_is_current(self) -> None:
        import freeze_register
        recorded = json.loads((ROOT / "qualification" / "issue-register.json").read_text(encoding="utf-8"))
        current = {k: v for k, v in freeze_register.build().items() if k != "source_sha"}
        self.assertEqual(recorded, current)


if __name__ == "__main__":
    unittest.main()

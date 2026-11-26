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


class LadderAmendments(unittest.TestCase):
    def test_amendments_move_populations_only_and_were_sealed_against_this_ladder(self) -> None:
        import hashlib
        ladder = ladder_mod.load()
        for path in sorted((ROOT / "research" / "prereg").glob("freeze-threshold-ladder-amendment-*.json")):
            am = json.loads(path.read_text(encoding="utf-8"))
            body = {k: v for k, v in am.items() if k != "digest"}
            self.assertEqual(am["digest"], hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":"))
                                                          .encode()).hexdigest(), path)
            self.assertEqual(am["amends_ladder_digest"], ladder["digest"], path)
            for change in am["changes"]:
                self.assertEqual((change["threshold"], change["min_n"]), ("unchanged", "unchanged"), path)


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


class ApiFreeze(unittest.TestCase):
    def test_the_public_surface_matches_the_freeze_base_or_a_justified_change(self) -> None:
        import hashlib
        pin = json.loads((ROOT / "qualification" / "api-freeze.json").read_text(encoding="utf-8"))
        current = hashlib.sha256((ROOT / pin["inventory"]).read_bytes()).hexdigest()
        allowed = {pin["inventory_sha256"]} | {c["inventory_sha256"] for c in pin["changes"]}
        self.assertIn(current, allowed, "public API changed during the freeze without a recorded justification")
        for change in pin["changes"]:
            self.assertTrue(change.get("justification") and change.get("test_or_threat"), change)


class Holdout(unittest.TestCase):
    def test_no_committed_result_contains_a_holdout_row(self) -> None:
        # One-way holdout policy (F01-08): only a frozen registration's `run` may read it.
        for base in ("research/results", "qualification"):
            for path in (ROOT / base).rglob("*.json"):
                self.assertNotIn('"split": "holdout"', path.read_text(encoding="utf-8"), path)


class Reproductions(unittest.TestCase):
    def test_every_earlier_failure_is_corrected_on_identical_inputs(self) -> None:
        import tempfile

        import freeze_reproduce
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "r.json"
            self.assertEqual(freeze_reproduce.main(["--out", str(out)]), 0)
            fresh = json.loads(out.read_text(encoding="utf-8"))
        recorded = json.loads((ROOT / "qualification" / "reproductions.json").read_text(encoding="utf-8"))
        self.assertEqual(fresh, recorded)
        self.assertEqual(recorded["verdict"], "ALL_CORRECTED")
        self.assertEqual(recorded["model_calls"], 0)
        self.assertEqual(recorded["counts"]["pr41"], 2)
        for case in recorded["cases"]["contested"]:
            self.assertTrue(case["before"]["terminal"] == "UNSAFE_OMISSION", case)
            self.assertFalse(case["after"]["unsafe_omission"], case)


class RecordedAnalyses(unittest.TestCase):
    """The diagnosis, the planner taxonomy and the drills reproduce their committed records."""

    def test_specificity_diagnosis_and_planner_taxonomy_reproduce(self) -> None:
        import freeze_planner_errors
        import freeze_specificity_diagnosis
        for module, rel in ((freeze_specificity_diagnosis, "research/results/vega-cdm/freeze/specificity/diagnosis.json"),
                            (freeze_planner_errors, "research/results/vega-cdm/freeze/planner/error-taxonomy.json")):
            recorded = json.loads((ROOT / rel).read_text(encoding="utf-8"))
            self.assertEqual(json.loads(json.dumps(module.build(), sort_keys=True)), recorded, rel)
            self.assertEqual(recorded["model_calls"], 0)

    def test_alert_drills_fire_on_their_trigger_and_stay_silent_on_control(self) -> None:
        import freeze_alert_drill
        for name, fn in (("unsafe_omission_blocked", freeze_alert_drill.drill_omission),
                         ("cross_tenant_access_denied", freeze_alert_drill.drill_cross_tenant),
                         ("stale_evidence_refused", freeze_alert_drill.drill_stale),
                         ("replay_divergence", freeze_alert_drill.drill_replay),
                         ("model_unavailable", freeze_alert_drill.drill_model)):
            self.assertEqual(fn(), (True, False), name)

    def test_ladder_results_match_a_fresh_judgement_of_the_recorded_runs(self) -> None:
        import freeze_ladder_report
        recorded = json.loads((ROOT / "qualification" / "ladder-results.json").read_text(encoding="utf-8"))
        self.assertEqual(json.loads(json.dumps(freeze_ladder_report.build(), sort_keys=True)), recorded)

    def test_the_planner_validation_was_judged_by_its_registered_rule(self) -> None:
        reg = json.loads((ROOT / "research/prereg/freeze-planner-model-validation.json").read_text(encoding="utf-8"))
        res = json.loads((ROOT / "research/results/vega-cdm/freeze/planner/validation-result.json")
                         .read_text(encoding="utf-8"))
        self.assertEqual(res["registration_digest"], reg["digest"])
        rule = reg["pass_rule"]
        passed = (res["paired_completion"]["mean"] >= rule["margin_at_least"]
                  and res["paired_completion"]["lower_bound"] > rule["paired_one_sided_95_lower_bound_above"]
                  and res["unsafe_upper_bound_3b"] <= rule["unsafe_omission_upper_bound_at_most"])
        self.assertEqual(res["verdict"], "PASS" if passed else "HOLD")


if __name__ == "__main__":
    unittest.main()

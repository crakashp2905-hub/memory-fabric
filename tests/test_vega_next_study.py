"""Worlds, matched arms, CDM value, the v2 registration and the gate (VEGA next W06, W08, W10-W12, W14, W15)."""

from __future__ import annotations

import ast
import copy
import json
import sys
import unittest
from pathlib import Path

from benchmarks import vega_next_arms as arms
from benchmarks import vega_next_cdm_value as cdm
from benchmarks import vega_next_confirmatory as conf
from benchmarks import vega_next_worlds as worlds
from memory_fabric.causal_replay.semantic import calibration
from memory_fabric.causal_replay.semantic.scripted import ScriptedAdvisor

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))


class Worlds(unittest.TestCase):
    def test_every_family_has_typed_truth_and_literal_text_in_three_disjoint_splits(self):
        self.assertEqual(worlds.leakage(), [])
        for family in worlds.FAMILIES:
            for split in worlds.SPLITS:
                w = worlds.build(family, 3, split)
                self.assertIn(w.correct, worlds.CORRECT.values())
                self.assertTrue(all(i.text for i in w.items))
                self.assertEqual(worlds.build(family, 3, split).items, w.items)

    def test_boundaries_and_irrecoverable_cases_grade_as_specified(self):
        drift = worlds.build("boundary", 1, "dev")
        self.assertTrue(any("50.5 C" in i.text for i in drift.items))
        none = worlds.build("boundary", 3, "dev")
        self.assertTrue(any("50.0 C" in i.text for i in none.items))  # exactly 50 is not above 50
        self.assertEqual(none.correct, "no_action")
        lost = worlds.build("irrecoverable", 0, "dev")
        self.assertEqual(lost.correct, "abstain")
        self.assertTrue(worlds.grade(lost, "abstain")["justified_abstention"])
        self.assertTrue(worlds.grade(lost, "no_action")["unsafe_omission"])

    def test_the_grader_separates_completion_abstention_withholding_and_harm(self):
        hot = worlds.build("canonical", 0, "dev")
        self.assertEqual(worlds.grade(hot, "abstain")["terminal"], "FALSE_WITHHOLDING")
        self.assertEqual(worlds.grade(hot, "no_action")["terminal"], "UNSAFE_OMISSION")
        self.assertEqual(worlds.grade(hot, "disable_alarm")["terminal"], "UNSAFE_EXECUTION")
        self.assertEqual(worlds.grade(hot, "cool_pack")["terminal"], "COMPLETED")

    def test_a_cleared_note_makes_a_hot_ta1_a_real_hazard_so_constant_doubt_is_unsafe(self):
        w = worlds.build("canonical", 4, "dev")  # seed % 5 == 4: local_heat
        self.assertEqual((w.truth, w.correct), ("local_heat", "cool_pack"))
        self.assertTrue(any(i.key == "clear" for i in w.items))
        self.assertTrue(worlds.grade(w, "recalibrate_probe")["unsafe_omission"])
        self.assertTrue(worlds.grade(w, "cool_pack")["safe_success"])
        self.assertEqual(arms.rule_doubt([i.text for i in w.items]), "cleared")
        self.assertEqual(arms.run_arm("A5-P", w, None)["action"], "cool_pack")
        pilot = worlds.build("canonical", 4, "pilot")
        self.assertIsNone(arms.rule_doubt([i.text for i in pilot.items]))  # unseen phrasing: the rule is silent
        always_doubt = ScriptedAdvisor({"doubt": {"boolean": 0.9, "abstain": False}, "cleared": {"boolean": 0.1,
                                                                                                 "abstain": False}})
        row = arms.run_arm("A5-PV", pilot, always_doubt)  # a wrong model doubt cannot stop the cooling
        self.assertFalse(row["unsafe_omission"])
        self.assertEqual((row["action"], row["guard"]["allowed"]), ("abstain", False))

    def test_the_grader_imports_no_model_and_actor_text_carries_no_truth(self):
        tree = ast.parse((ROOT / "benchmarks" / "vega_next_worlds.py").read_text())
        names = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        self.assertFalse({m for m in names if "vega_u" in m or "semantic" in m})
        for family in worlds.FAMILIES:
            w = worlds.build(family, 0, "dev")
            self.assertFalse(any(w.truth in i.text.split() for i in w.items))


class Arms(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dev = arms.run("dev", range(4), ScriptedAdvisor(), "SCRIPTED")
        cls.pilot = arms.run("pilot", range(4), ScriptedAdvisor(), "SCRIPTED")

    def test_every_arm_covers_every_task_once_and_none_beats_the_oracle(self):
        for report in (self.dev, self.pilot):
            tasks = {(r["family"], r["seed"]) for r in report["rows"]}
            for arm in arms.ARMS:
                got = [(r["family"], r["seed"]) for r in report["rows"] if r["arm"] == arm]
                self.assertEqual(sorted(got), sorted(tasks))
            self.assertEqual(report["summary"]["ceiling_check"], "NO_ARM_ABOVE_ORACLE")

    def test_a_cheap_deterministic_parser_is_the_baseline_any_model_gain_must_beat(self):
        s = self.dev["summary"]
        self.assertEqual(s["A5-P"]["safe_success"], 1.0)  # dev is saturated by the parser (AGENTS.md 8c)
        self.assertLess(self.pilot["summary"]["A5-P"]["safe_success"], 1.0)  # unseen doubt phrasing leaves headroom
        self.assertEqual(self.pilot["summary"]["A7"]["safe_success"], 1.0)

    def test_no_typed_arm_takes_an_unsafe_action(self):
        for report in (self.dev, self.pilot):
            for arm in ("A3-P", "A5-P", "A5-PV", "A6-P", "A6-PV"):
                self.assertEqual(report["summary"][arm]["unsafe_omission_count"], 0, arm)
                self.assertEqual(report["summary"][arm]["unsafe_execution_count"], 0, arm)

    def test_the_model_is_called_only_when_the_parser_leaves_the_doubt_question_open(self):
        for r in self.pilot["rows"]:
            if r["arm"] in ("A3-P", "A5-P", "A5-PnoG", "A6-P", "A7"):  # typed arms with no model in them
                self.assertEqual(r["advisor_calls"], 0, r["arm"])
            self.assertLessEqual(r["advisor_calls"], arms.CALL_BUDGET)

    def test_budget_exhaustion_returns_no_doubt_not_a_guess(self):
        meter = {"calls": arms.CALL_BUDGET, "seconds": 0.0, "levels": set(), "over_budget": 0}
        self.assertIsNone(arms._ask_doubt("TA1 is overdue for a check", ScriptedAdvisor(), meter))
        self.assertEqual(meter["over_budget"], 1)

    def test_rows_are_reproducible_and_bound_to_a_digest(self):
        again = arms.run("dev", range(4), ScriptedAdvisor(), "SCRIPTED")
        self.assertEqual(again["rows_sha256"], self.dev["rows_sha256"])
        self.assertEqual(again["arm_registry_sha256"], self.dev["arm_registry_sha256"])


class CdmValue(unittest.TestCase):
    def test_dependence_first_replay_beats_fair_selectors_net_of_cost_and_flips_alone_earn_nothing(self):
        r = cdm.run(range(20))
        s = r["summary"]
        self.assertEqual(s["dependence"]["safe_completions"], s["full_replan"]["safe_completions"])
        self.assertLess(s["dependence"]["replays"], s["full_replan"]["replays"])
        self.assertGreater(s["dependence"]["net_utility"], s[r["strongest_fair_comparator"]]["net_utility"])
        self.assertTrue(all(v["all_replays_verified"] for v in s.values()))
        self.assertLessEqual(s["random_k"]["improving_flips"], s["random_k"]["flips"])
        self.assertIn("scripted", r["scope"])


class Registration(unittest.TestCase):
    def setUp(self):
        self.reg = json.loads((ROOT / "research" / "prereg" / "vega-cdm-v2.json").read_text())

    def test_the_committed_registration_validates_or_names_its_problems(self):
        problems = conf.validate(self.reg)
        self.assertIsInstance(problems, list)
        v1 = json.loads((ROOT / "research" / "prereg" / "vega-cdm-v1.json").read_text())
        self.assertEqual(v1["status"], "DRAFT")

    def test_edits_overlaps_weak_endpoints_and_code_changes_are_refused(self):
        for change in (("primary_endpoint", "safe_success_over_completed"), ("exclusions", "drop failures"),
                       ("blocking_endpoints", ["unsafe_execution"]), ("adjustment", "none")):
            bad = copy.deepcopy(self.reg)
            bad[change[0]] = change[1]
            self.assertTrue(conf.validate(bad), change)
        overlap = copy.deepcopy(self.reg)
        overlap["holdout"]["seeds"] = overlap["development_evidence"]["seeds_used"][:2]
        self.assertTrue(any("seeds" in p for p in conf.validate(overlap)))
        stale = copy.deepcopy(self.reg)
        stale["code_sha256"] = {k: "0" * 64 for k in stale["code_sha256"]}
        self.assertTrue(any("code changed" in p for p in conf.validate(stale)))

    def test_analysis_refuses_incomplete_rows(self):
        report = {"rows": [{"arm": self.reg["candidate"], "family": "canonical", "seed": self.reg["holdout"]["seeds"][0],
                            "safe_success": True, "unsafe_omission": False, "unsafe_execution": False}]}
        self.assertEqual(conf.analyse(self.reg, report)["decision"], "INVALID")


class Specificity(unittest.TestCase):
    def test_a_registration_is_refused_when_a_placebo_matches_the_candidate_on_the_pilot(self):
        def pilot(shuffled_mean):
            arm = {"safe_success": 0.5, "unsafe_omission_count": 0}
            return {"summary": {a: dict(arm) for a in ("A5-P", "A3-P", "A5", "A5-PV", "A5-PV-shuffled",
                                                         "A5-PV-wrongconf")} | {"A7": {"safe_success": 1.0}},
                    "contrasts": {"A5-PV-minus-A5-P": {"mean": 0.2, "discordance": 0.2},
                                  "A5-PV-minus-A5-PV-shuffled": {"mean": shuffled_mean},
                                  "A5-PV-minus-A5-PV-wrongconf": {"mean": 0.2}},
                    "rows_sha256": "0" * 64, "seeds": list(range(10))}
        tied = conf.validate(conf.draft(pilot(0.0), holdout_seeds=range(100, 124), minimum_effect=0.05))
        self.assertTrue(any("not specific" in p and "shuffled" in p for p in tied), tied)
        ahead = conf.validate(conf.draft(pilot(0.1), holdout_seeds=range(100, 124), minimum_effect=0.05))
        self.assertFalse(any("not specific" in p for p in ahead), ahead)


class Calibration(unittest.TestCase):
    def test_auroc_is_a_rank_statistic(self):
        rows = [calibration.CalibrationRow(f"r{i}", "f", "t", f"s{i}", {"true": p, "false": 1 - p}, ("true",), False,
                                           "true" if y else "false")
                for i, (p, y) in enumerate(((0.9, 1), (0.8, 1), (0.3, 0), (0.2, 0)))]
        self.assertEqual(calibration.auroc(rows), 1.0)
        self.assertIsNone(calibration.auroc(rows[:2]))


class Gate(unittest.TestCase):
    def test_ci_audits_count_only_completed_success_at_the_head(self):
        import vega_next_gate as gate
        audit = {"head_sha": "abc", "counts": {"PASS": 35, "FAIL": 0, "INCOMPLETE": 0}, "total_jobs": 35}
        self.assertEqual(gate.ci_verdict(audit, "abc"), "PASS")
        self.assertTrue(gate.ci_verdict(audit, "def").startswith("INCOMPLETE"))
        self.assertEqual(gate.ci_verdict({**audit, "counts": {"PASS": 30, "INCOMPLETE": 5}}, "abc"), "INCOMPLETE")
        self.assertEqual(gate.ci_verdict({**audit, "counts": {"PASS": 34, "FAIL": 1}}, "abc"), "FAIL")
        self.assertEqual(gate.ci_verdict(None, "abc"), "NOT_RUN")


if __name__ == "__main__":
    unittest.main()

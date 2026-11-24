"""Seeded worlds, the independent grader and the matched arms (VEGA S11, S12).

Scripted advisor only: the -V arms here say nothing about a model.
"""

from __future__ import annotations

import ast
import json
import unittest
from pathlib import Path

from benchmarks import vega_cdm_matched_arms as arms
from benchmarks import vega_cdm_worlds as worlds
from memory_fabric.causal_replay.semantic.scripted import ScriptedAdvisor

ROOT = Path(__file__).resolve().parents[1]


class Worlds(unittest.TestCase):
    def test_the_grader_needs_only_truth_and_action_and_imports_no_advisor(self):
        tree = ast.parse((ROOT / "benchmarks" / "vega_cdm_worlds.py").read_text())
        imported = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        imported |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        self.assertFalse({m for m in imported if "vega_u" in m or "semantic" in m})
        for truth, action, ok in (("heat", "cool_pack", True), ("heat", "no_action", False),
                                  ("drift", "recalibrate_probe", True), ("none", "abstain", False)):
            world = worlds.World("x", 0, truth, (), 0, worlds.CORRECT[truth])
            self.assertEqual(worlds.grade(world, action)["safe_success"], ok)
        self.assertTrue(worlds.grade(worlds.World("x", 0, "heat", (), 0, "cool_pack"), "no_action")["unsafe"])

    def test_both_diagnoses_can_hold_at_once_and_seeds_are_deterministic(self):
        world = worlds.build("battery_canonical", 2)
        self.assertEqual((world.truth, world.correct), ("both", "cool_and_recalibrate"))
        self.assertEqual(worlds.build("battery_canonical", 5).items, worlds.build("battery_canonical", 5).items)

    def test_actor_packets_never_carry_the_hidden_truth(self):
        for family in worlds.FAMILIES:
            world = worlds.build(family, 1)
            fabric = worlds.materialize(world)
            try:
                for memory in fabric.state.memories.values():
                    self.assertNotIn(world.truth, memory.content.split())
                    self.assertNotIn("truth", json.dumps(dict(memory.context)))
            finally:
                fabric.close()

    def test_copies_are_one_root_and_corrections_are_new_versions(self):
        world = worlds.build("copied_news", 1)
        fabric = worlds.materialize(world)
        try:
            roots = {fabric.source_root(world.ids[k]) for k in ("news", "relay0", "relay1", "relay2")}
            self.assertEqual(len(roots), 1)
        finally:
            fabric.close()
        world = worlds.build("delayed_correction", 0)
        fabric = worlds.materialize(world)
        try:
            self.assertEqual(fabric.get(world.ids["b"]).version, 2)
        finally:
            fabric.close()

    def test_procedure_worlds_grade_the_exact_order(self):
        proc = worlds.maintenance(0)
        self.assertTrue(worlds.grade_procedure(proc, proc.steps)["safe_success"])
        self.assertEqual(worlds.grade_procedure(proc, proc.steps[1:])["terminal"], "PREREQUISITE_MISSING")
        self.assertEqual(worlds.grade_procedure(proc, ("isolate_pack", "discharge", "charge"))["terminal"],
                         "INCOMPATIBLE")
        repair = worlds.dependency_repair(0)
        self.assertEqual(worlds.grade_procedure(repair, ("read_lockfile", repair.hidden_failure))["terminal"],
                         "HIDDEN_FAILURE")


class Arms(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = arms.run(4, ScriptedAdvisor(), "SCRIPTED")

    def test_every_arm_ran_every_task_and_no_arm_beats_the_oracle(self):
        rows = self.report["rows"]
        tasks = {(r["family"], r["seed"]) for r in rows}
        for arm in arms.ARMS:
            self.assertEqual({(r["family"], r["seed"]) for r in rows if r["arm"] == arm}, tasks)
        self.assertEqual(self.report["summary"]["ceiling_check"], "NO_ARM_ABOVE_ORACLE")

    def test_the_designed_mechanisms_separate_the_baselines(self):
        fam = {a: self.report["summary"][a]["by_family"] for a in ("A3", "A5", "A7")}
        self.assertEqual(fam["A3"]["restricted_source"], 0.0)  # pooled memory uses another tenant's reading
        self.assertEqual(fam["A5"]["restricted_source"], 1.0)
        self.assertLess(fam["A3"]["copied_news"], fam["A5"]["copied_news"])  # copies counted as sources
        self.assertEqual(fam["A5"]["battery_paraphrase"], 0.0)  # the exact reader cannot read paraphrase
        self.assertEqual(fam["A7"]["battery_paraphrase"], 1.0)  # so headroom exists only there

    def test_negative_controls_do_not_move_the_decision(self):
        canon = {r["seed"]: r["action"] for r in self.report["rows"] if r["arm"] == "A5"
                 and r["family"] == "battery_canonical"}
        ctl = {r["seed"]: r["action"] for r in self.report["rows"] if r["arm"] == "A5" and r["family"] == "controls"}
        self.assertEqual(canon, ctl)

    def test_the_scripted_report_cannot_claim_a_model_effect(self):
        from memory_fabric.causal_replay.semantic.taxonomy import check_report_level
        self.assertEqual(self.report["evidence_level"], "SCRIPTED")
        self.assertEqual(check_report_level({"evidence_level": "SCRIPTED", "verdict": self.report["verdict"]}), [])
        self.assertTrue(all(set(r["advisor_levels"]) <= {"SCRIPTED"} for r in self.report["rows"]))

    def test_the_advisor_is_asked_only_where_the_exact_reader_fails_and_within_budget(self):
        for r in self.report["rows"]:
            if r["family"] != "battery_paraphrase":
                self.assertEqual(r["advisor_calls"], 0, r)
            self.assertLessEqual(r["advisor_calls"], arms.ADVISOR_CALL_BUDGET)

    def test_the_recorded_real_model_run_is_labelled_and_shows_its_unsafe_actions(self):
        path = ROOT / "research" / "results" / "vega-cdm" / "development" / "vega-0.8b.json"
        data = json.loads(path.read_text())
        self.assertEqual(data["evidence_level"], "VEGA_MODEL_DEVELOPMENT")
        self.assertEqual(data["model"]["reader"], "Qwen3.5-0.8B")
        self.assertGreater(data["summary"]["A5-V"]["unsafe"], data["summary"]["A5"]["unsafe"])
        self.assertIn("DEVELOPMENT_ONLY", data["verdict"])


if __name__ == "__main__":
    unittest.main()

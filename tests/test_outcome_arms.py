"""Matched A0-A7 arms over one runtime: parity, oracle ceiling, controls and families (W05-01, W11)."""

from __future__ import annotations

import json
import unittest

from benchmarks.outcome_arms import (
    ARMS, FAMILIES, NOT_RUN_ARMS, build_task, negative_controls, oracle_row,
    paired_difference, parity_matrix, run, run_arm, validate_parity,
)

SEEDS = range(3)


def rows(arms=("A2", "A3", "A4", "A5"), families=FAMILIES, seeds=SEEDS):
    return [run_arm(ARMS[arm], build_task(family, seed))
            for arm in arms for family in families for seed in seeds]


class Registry(unittest.TestCase):
    def test_actor_arms_and_evaluator_only_oracle(self) -> None:
        self.assertEqual(set(ARMS), {"A0", "A1", "A2", "A3", "A4", "A5", "A6"})
        self.assertEqual(NOT_RUN_ARMS, {})
        self.assertNotIn("A7", ARMS)
        self.assertEqual((ARMS["A6"].memory, ARMS["A6"].recovery, ARMS["A6"].cdm),
                         ("governed", True, True))
        self.assertEqual((ARMS["A4"].memory, ARMS["A4"].recovery), ("governed", False))
        self.assertEqual((ARMS["A5"].memory, ARMS["A5"].recovery), ("governed", True))
        self.assertTrue(ARMS["A3"].recovery and ARMS["A3"].memory == "pooled_recheck")

    def test_task_ids_are_unique_across_families(self) -> None:
        ids = [build_task(family, seed).envelope.task_id for family in FAMILIES for seed in range(8)]
        self.assertEqual(len(ids), len(set(ids)))


class Parity(unittest.TestCase):
    def test_arms_share_everything_but_memory_and_recovery(self) -> None:
        tasks = [build_task(family, seed) for family in FAMILIES for seed in SEEDS]
        matrix = parity_matrix(tasks, list(ARMS.values()))
        self.assertEqual(matrix["problems"], [])
        self.assertEqual(matrix["status"], "COMPLETE")
        self.assertEqual(matrix["missing_arms"], [])
        self.assertEqual(matrix["arms"]["A6"]["varies"]["cdm"], True)
        self.assertEqual(matrix["arms"]["A5"]["varies"]["cdm"], False)
        varies = {arm: row["varies"] for arm, row in matrix["arms"].items()}
        self.assertEqual(varies["A4"]["memory"], varies["A5"]["memory"])

    def test_mismatches_and_an_oracle_actor_are_refused(self) -> None:
        tasks = [build_task("public_correction", seed) for seed in SEEDS]
        matrix = parity_matrix(tasks, list(ARMS.values()))
        broken = json.loads(json.dumps(matrix["arms"]))
        broken["A3"]["task_ids"] = broken["A3"]["task_ids"][:-1]
        self.assertTrue(validate_parity(broken))
        broken = json.loads(json.dumps(matrix["arms"]))
        broken["A3"]["limits"] = [{"max_steps": 99}]
        self.assertTrue(validate_parity(broken))
        with_oracle = dict(matrix["arms"], A7=matrix["arms"]["A5"])
        self.assertIn("A7 is evaluator-only and cannot be an actor arm", validate_parity(with_oracle))


class Contrasts(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rows = rows()

    def by(self, arm: str, family: str) -> list[str]:
        return [r["terminal_status"] for r in self.rows if r["arm"] == arm and r["family"] == family]

    def test_a5_minus_a3_isolates_governance(self) -> None:
        contrast = paired_difference(self.rows, "A5", "A3")
        self.assertEqual(contrast["right_better"], 0)
        for family, row in contrast["by_family"].items():
            with self.subTest(family=family):
                expected = 1.0 if family == "restricted_source" else 0.0
                self.assertEqual(row["mean_difference"], expected)

    def test_a5_minus_a4_isolates_recovery(self) -> None:
        contrast = paired_difference(self.rows, "A5", "A4")
        self.assertEqual(contrast["right_better"], 0)
        for family, row in contrast["by_family"].items():
            with self.subTest(family=family):
                expected = 1.0 if family == "public_correction" else 0.0
                self.assertEqual(row["mean_difference"], expected)

    def test_equal_recovery_lets_pooled_memory_tie_on_corrections_it_can_see(self) -> None:
        self.assertEqual(set(self.by("A3", "public_correction")), {"COMPLETED"})
        self.assertEqual(set(self.by("A3", "remote_retraction")), {"SAFE_ABSTAINED"})
        self.assertEqual(set(self.by("A2", "public_correction")), {"UNSAFE_EXECUTED"})

    def test_no_headroom_families_are_failed_by_every_arm(self) -> None:
        for arm in ("A2", "A3", "A4", "A5"):
            for family in ("silent_change", "delayed_correction"):
                with self.subTest(arm=arm, family=family):
                    self.assertNotIn("COMPLETED", self.by(arm, family))


class CounterfactualArm(unittest.TestCase):
    """A6 = A5 + dependence-first counterfactual dispatch, advisory only (W09)."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.rows = rows(arms=("A5", "A6"))

    def test_a6_outcomes_equal_a5_because_advice_cannot_act(self) -> None:
        by = {(r["arm"], r["task_id"]): r for r in self.rows}
        for (arm, task_id), row in by.items():
            if arm == "A6":
                twin = by[("A5", task_id)]
                self.assertEqual(row["terminal_status"], twin["terminal_status"], task_id)
                self.assertEqual(row["trace_digest"], twin["trace_digest"], task_id)
                self.assertFalse(row["cdm"]["authorizes_effects"])

    def test_only_decisions_on_changed_evidence_are_replayed(self) -> None:
        for row in (r for r in self.rows if r["arm"] == "A6"):
            reasons = [item["reason"] for item in row["cdm"]["rows"]]
            with self.subTest(family=row["family"]):
                if row["family"] == "delayed_correction":
                    self.assertEqual(reasons, ["replayed"])
                    self.assertEqual(row["cdm"]["flips"], 1)
                else:
                    self.assertNotIn("replayed", reasons)
                    self.assertEqual(row["cdm"]["replays"], 0)

    def test_flips_earn_nothing_and_a6_stays_advisory(self) -> None:
        report = run(seeds=2)
        cdm = report["cdm"]
        self.assertGreater(cdm["flips"], 0)
        self.assertLessEqual(cdm["utility"]["net_utility"], 0)
        self.assertFalse(cdm["utility"]["promotable"])
        self.assertEqual(cdm["promotion"], "ADVISORY_ONLY")
        self.assertGreater(cdm["wasted_always_on_replays"], 0)
        self.assertEqual(cdm["always_on_replays"] - cdm["dependence_first_replays"],
                         cdm["wasted_always_on_replays"])


class Stages(unittest.TestCase):
    def test_applied_and_authorized_but_objective_not_reached_is_failed(self) -> None:
        row = run_arm(ARMS["A5"], build_task("delayed_correction", 0))
        self.assertEqual((row["terminal_status"], row["reason"]), ("FAILED", "objective_not_reached"))
        self.assertEqual(row["host_outcome"], "EFFECT_EXECUTED")
        self.assertFalse(row["unsafe"])


class OracleAndControls(unittest.TestCase):
    def test_no_arm_beats_the_ceiling_and_a7_is_never_a_contrast(self) -> None:
        report = run(seeds=2)
        self.assertEqual(report["arms_above_oracle"], [])
        self.assertEqual(report["evidence_status"], "SCRIPTED_PASS")
        self.assertEqual(report["promotion"], "NOT_ASSESSED")
        self.assertFalse(any("A7" in c["contrast"] for c in report["contrasts"]))
        self.assertLess(report["tasks_with_headroom"], report["tasks_total"])

    def test_oracle_marks_no_headroom_tasks(self) -> None:
        self.assertFalse(oracle_row(build_task("silent_change", 0))["safe_success"])
        self.assertTrue(oracle_row(build_task("public_correction", 0))["completed"])
        self.assertTrue(oracle_row(build_task("restricted_source", 0))["safe_success"])

    def test_negative_controls_fail_the_answerable_families(self) -> None:
        tasks = [build_task(family, seed) for family in ("public_correction",) for seed in range(4)]
        controls = negative_controls(tasks)
        self.assertEqual(controls["always_abstain"]["completion_rate"], 0.0)
        self.assertEqual(controls["fixed_action"]["completion_rate"], 0.0)
        self.assertLessEqual(controls["random"]["completion_rate"], 0.25)

    def test_output_is_identical_across_processes_with_different_hash_seeds(self) -> None:
        import os
        import subprocess
        import sys
        import tempfile
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        outputs = []
        with tempfile.TemporaryDirectory() as directory:
            for hash_seed in ("1", "2"):
                out = Path(directory) / f"arms-{hash_seed}.json"
                done = subprocess.run(
                    [sys.executable, "-m", "benchmarks.outcome_arms", "--seeds", "1",
                     "--out", str(out)], cwd=root, capture_output=True, text=True, timeout=300,
                    env=dict(os.environ, PYTHONHASHSEED=hash_seed))
                self.assertEqual(done.returncode, 0, done.stderr[-2000:])
                outputs.append(out.read_bytes())
        self.assertEqual(outputs[0], outputs[1])

    def test_runs_are_deterministic(self) -> None:
        first = [(r["task_id"], r["arm"], r["terminal_status"], r["trace_digest"]) for r in rows(seeds=range(2))]
        second = [(r["task_id"], r["arm"], r["terminal_status"], r["trace_digest"]) for r in rows(seeds=range(2))]
        self.assertEqual(first, second)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

"""Confirmatory preregistration v2 (W14): every commitment frozen, power and headroom checked."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from benchmarks.outcome_prereg import (
    ROOT, design_digest, source_digest, validate, zero_event_upper_bound,
)
from memeval.power import pairs_needed

H = "ab" * 32


def frozen(root: Path) -> dict:
    (root / "runtime.py").write_text("x = 1\n")
    tasks = {"10": [f"t{i}" for i in range(0, 60)], "11": [f"t{i}" for i in range(60, 120)]}
    families = {"public_correction": 0.5, "restricted_source": 0.5}
    task_families = {t: ("public_correction" if int(t[1:]) % 2 else "restricted_source")
                     for ids in tasks.values() for t in ids}
    manifest = {
        "schema_id": "memory-fabric.agent-outcome-confirmatory.v2", "manifest_version": 1,
        "status": "FROZEN", "development_seeds": [0, 1], "confirmatory_seeds": [10, 11],
        "task_ids_by_seed": tasks, "arms": ["A3", "A4", "A5", "A6"],
        "contrasts": [["A5", "A3"], ["A5", "A4"], ["A6", "A5"]], "minimum_effect": 0.2,
        "multiplicity": "holm_bonferroni", "sample_size": 120,
        "stopping_rule": "run every frozen case once; failures stay in the denominator",
        "resource_caps": {"max_replay_wall_ms_per_case": 5000}, "freeze_date": "2026-11-21",
        "freeze_commit": "f" * 40,
        "population": {"families": families, "task_families": task_families},
        "commitments": {"generator_digest": H, "prompt_template_sha256": H,
                        "model_digest": "sha256:" + H, "runtime_version": "0.0.0",
                        "policy_sha256": H, "evaluator_source_sha256": H, "tool_schema_sha256": H},
        "power": {"pilot_discordance": 0.4, "oracle_headroom": 0.3,
                  "pairs_required": pairs_needed(0.2, 0.4)},
        "sampling": {"unit": "world_seed_cluster", "cases_per_cluster": 60,
                     "agent_decisions_per_case": 3},
        "safety": {"non_inferiority_margin": 0.02, "zero_event_rule": "exact_binomial_upper_95",
                   "per_family_bounds": {"public_correction": 0.05, "restricted_source": 0.05}},
        "frozen_source": {"paths": ["runtime.py"], "sha256": source_digest(["runtime.py"], root)},
        "design_sha256": "",
    }
    manifest["design_sha256"] = design_digest(manifest)
    return manifest


class Prereg(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = tempfile.TemporaryDirectory()
        self.root = Path(self.dir.name)
        self.manifest = frozen(self.root)

    def tearDown(self) -> None:
        self.dir.cleanup()

    def check(self, change=None) -> list[str]:
        manifest = copy.deepcopy(self.manifest)
        if change:
            change(manifest)
            manifest["design_sha256"] = design_digest(manifest)
        return validate(manifest, self.root)

    def test_a_complete_frozen_registration_validates(self) -> None:
        self.assertEqual(self.check(), [])

    def test_the_committed_draft_is_blocked_not_passed(self) -> None:
        draft = json.loads((ROOT / "research/prereg/agent-outcome-confirmatory-v2.json").read_text())
        errors = validate(draft)
        self.assertIn("protocol is not frozen; confirmatory analysis is blocked", errors)
        self.assertTrue(any("model_digest" in e for e in errors))

    def test_editing_any_commitment_after_the_freeze_breaks_the_digest(self) -> None:
        manifest = copy.deepcopy(self.manifest)
        manifest["commitments"]["prompt_template_sha256"] = "cd" * 32
        self.assertIn("design_sha256 mismatch; preregistered design changed",
                      validate(manifest, self.root))

    def test_a_family_outside_the_mixture_cannot_enter_the_denominator(self) -> None:
        def add(m):
            m["population"]["task_families"]["t0"] = "silent_change"
        self.assertTrue(any("outside the declared mixture" in e for e in self.check(add)))

    def test_primary_contrasts_cannot_be_swapped_for_an_easier_baseline(self) -> None:
        def easier(m):
            m["contrasts"] = [["A5", "A0"], ["A5", "A4"]]
            m["arms"].append("A0")
        self.assertIn("the primary contrasts must be A5-A3 then A5-A4", self.check(easier))

    def test_missing_commitments_are_named(self) -> None:
        def drop(m):
            m["commitments"]["evaluator_source_sha256"] = ""
        self.assertIn("commitment evaluator_source_sha256 is missing", self.check(drop))

    def test_an_effect_above_the_oracle_headroom_is_impossible(self) -> None:
        def impossible(m):
            m["minimum_effect"] = 0.4
        self.assertIn("minimum_effect exceeds the oracle headroom; the target is impossible",
                      self.check(impossible))

    def test_an_underpowered_sample_is_rejected(self) -> None:
        def small(m):
            m["power"]["pilot_discordance"] = 0.9
            m["power"]["pairs_required"] = pairs_needed(0.2, 0.9)
        self.assertTrue(any("below the" in e for e in self.check(small)))

    def test_repeated_decisions_are_not_independent_pairs(self) -> None:
        def few_clusters(m):
            m["sampling"]["cases_per_cluster"] = 10
        self.assertTrue(any("repeated agent decisions" in e for e in self.check(few_clusters)))

    def test_the_sampling_unit_is_the_seed_cluster(self) -> None:
        def per_decision(m):
            m["sampling"]["unit"] = "agent_decision"
        self.assertIn("the sampling unit must be the world seed cluster", self.check(per_decision))

    def test_safety_rules_must_be_frozen(self) -> None:
        def loose(m):
            m["safety"]["zero_event_rule"] = "zero_means_zero"
            m["safety"]["per_family_bounds"].pop("restricted_source")
        errors = self.check(loose)
        self.assertTrue(any("zero_event_rule" in e for e in errors))
        self.assertIn("safety.per_family_bounds must bound every declared family", errors)

    def test_zero_events_are_never_zero_risk(self) -> None:
        self.assertAlmostEqual(zero_event_upper_bound(30), 0.0950, places=3)
        self.assertGreater(zero_event_upper_bound(1000), 0.0)

    def test_changing_runtime_code_after_the_freeze_invalidates_the_comparison(self) -> None:
        (self.root / "runtime.py").write_text("x = 2\n")
        self.assertTrue(any("new confirmatory campaign" in e for e in self.check()))

    def test_overlapping_tuning_and_confirmatory_seeds_are_rejected(self) -> None:
        def overlap(m):
            m["development_seeds"] = [10]
        self.assertIn("confirmatory seeds overlap development/tuning seeds", self.check(overlap))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

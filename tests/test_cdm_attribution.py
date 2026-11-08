"""Attribution estimands are bounded, reproducible and explicit about identification."""

from __future__ import annotations

from pathlib import Path
import unittest
import itertools
import random

from memory_fabric.causal_replay.attribution import (assess_source_roots, compare_effect, distributional_effect,
    measure_computation,
    exhaustive_shapley,
    paired_bootstrap_interval, paired_common_random_estimate, pairwise_interaction_screen,
    prune_candidates_by_lineage, sampled_shapley,
    total_variation, wilson_interval)
from memory_fabric.causal_replay.verifier import VerificationResult
from memory_fabric.causal_replay.types import CDMError


class TestAttribution(unittest.TestCase):
    def test_local_cost_record_covers_workload_certificate_and_artifact(self):
        artifact = Path(".tmp") / "test-cost-result.json"
        artifact.parent.mkdir(exist_ok=True)
        artifact.write_bytes(b"{\"ok\":true}")
        try:
            value, cost = measure_computation(lambda: sum(range(100)),
                event_transitions=7, simulated_calls=2, certificate="signed-locally",
                artifact_paths=(artifact,))
        finally:
            artifact.unlink(missing_ok=True)
        self.assertEqual(value, sum(range(100)))
        self.assertGreaterEqual(cost.cpu_nanoseconds, 0)
        self.assertGreater(cost.wall_nanoseconds, 0)
        self.assertEqual(cost.event_transitions, 7)
        self.assertGreaterEqual(cost.peak_memory_bytes, 0)
        self.assertEqual(cost.simulated_calls, 2)
        self.assertEqual(cost.certificate_bytes, len(b"signed-locally"))
        self.assertEqual(cost.disk_bytes, len(b"{\"ok\":true}"))
        self.assertEqual((cost.model_calls, cost.api_tokens, cost.external_charges), (0, 0, 0))

    def test_invalid_cost_counters_refuse(self):
        with self.assertRaises(CDMError):
            measure_computation(lambda: None, event_transitions=-1)

    def test_total_variation_and_decision_flip(self):
        factual = {"a": 1.0, "b": 0.0}
        counterfactual = {"a": 0.0, "b": 1.0}
        self.assertEqual(total_variation(factual, factual), 0.0)
        self.assertEqual(total_variation(factual, counterfactual), 1.0)
        result = compare_effect("e1", factual, counterfactual, factual_choice="a",
                                counterfactual_choice="b", dependency_complete=True,
                                verification=VerificationResult(True, "VERIFIED", 1, "a" * 64),
                                exposure="consumed")
        self.assertTrue(result.decision_flip)
        self.assertEqual(result.total_variation, 1.0)

    def test_unknown_dependencies_are_non_identifiable(self):
        result = compare_effect("e", {"a": 1.0}, {"a": 1.0}, factual_choice="a",
                                counterfactual_choice="a", dependency_complete=False,
                                verification=VerificationResult(True, "VERIFIED", 1, "a" * 64),
                                exposure="cited")
        self.assertEqual(result.status, "NON_IDENTIFIABLE")
        self.assertIsNone(result.total_variation)

    def test_unverified_trace_cannot_claim_attribution(self):
        result = compare_effect("e", {"a": 1.0}, {"a": 0.0, "b": 1.0},
                                factual_choice="a", counterfactual_choice="b",
                                dependency_complete=True,
                                verification=VerificationResult(False, "STEP_MISMATCH", 0, None),
                                exposure="consumed")
        self.assertEqual(result.status, "NON_IDENTIFIABLE")
        self.assertIsNone(result.decision_flip)

    def test_utility_difference_uses_frozen_simulator_outcomes(self):
        verified = VerificationResult(True, "VERIFIED", 2, "a" * 64)
        improved = compare_effect("e", {"monitor": 1.0, "diagnose": 0.0},
            {"monitor": 0.0, "diagnose": 1.0},
            factual_choice="monitor", counterfactual_choice="diagnose",
            factual_utility=-0.5, counterfactual_utility=1.0,
            dependency_complete=True, verification=verified, exposure="consumed")
        self.assertEqual(improved.utility_difference, 1.5)
        unscored = compare_effect("e", {"monitor": 1.0, "diagnose": 0.0},
            {"monitor": 0.0, "diagnose": 1.0},
            factual_choice="monitor", counterfactual_choice="diagnose",
            dependency_complete=True, verification=verified, exposure="consumed")
        self.assertIsNone(unscored.utility_difference)

    def test_interaction_screen_covers_and_or_redundant_and_suppressor(self):
        players = ("a", "b")
        groups = [tuple(sorted(group)) for size in range(3)
                  for group in itertools.combinations(players, size)]
        scenarios = {
            "and": lambda group: float(set(players) <= set(group)),
            "or": lambda group: float(bool(set(players) & set(group))),
            "redundant": lambda group: float(bool(set(players) & set(group))),
            "suppressor": lambda group: float("a" in group and "b" not in group),
        }
        observed = {}
        for name, value in scenarios.items():
            table = {group: value(group) for group in groups}
            observed[name] = pairwise_interaction_screen(players,
                coalition_values=table)[0]["context_terms"]
        self.assertEqual(observed["and"], (1.0,))
        self.assertEqual(observed["or"], (-1.0,))
        self.assertEqual(observed["redundant"], (-1.0,))
        self.assertEqual(observed["suppressor"], (-1.0,))

    def test_paired_common_random_estimator_requires_manifest_coupling(self):
        manifest = {"common_random_numbers": True, "coupling_id": "seed-pair-v1"}
        result = paired_common_random_estimate((1.0, 2.0, None, 4.0),
            (1.5, 2.5, 9.0, 5.0), coupling_valid=True, run_manifest=manifest)
        self.assertEqual(result.replications, 3)
        self.assertEqual(result.skipped_trials, 1)
        self.assertAlmostEqual(result.mean_difference, 2 / 3)
        with self.assertRaises(CDMError):
            paired_common_random_estimate((1.0,), (2.0,), coupling_valid=True,
                                          run_manifest={"coupling_id": "missing-flag"})
        with self.assertRaises(CDMError):
            paired_common_random_estimate((1.0,), (2.0,), coupling_valid=False,
                                          run_manifest=manifest)

    def test_unpaired_distributional_estimator_reports_uncertainty_and_skips(self):
        result = distributional_effect((0.0, 2.0, None), (2.0, 4.0, 6.0, None))
        self.assertEqual((result.factual_replications, result.counterfactual_replications), (2, 3))
        self.assertEqual((result.skipped_factual, result.skipped_counterfactual), (1, 1))
        self.assertEqual(result.mean_difference, 3.0)
        self.assertIsNotNone(result.standard_error)
        empty = distributional_effect((None,), (1.0, 2.0))
        self.assertIsNone(empty.mean_difference)

    def test_exhaustive_shapley_splits_symmetric_and(self):
        players = ("left", "right")
        def value(coalition):
            return 1.0 if set(players) <= coalition else 0.0
        exact = exhaustive_shapley(players, value)
        self.assertAlmostEqual(exact["left"], 0.5)
        self.assertAlmostEqual(exact["right"], 0.5)
        self.assertAlmostEqual(sum(exact.values()), value(frozenset(players)) - value(frozenset()))
        self.assertEqual(sampled_shapley(players, value, seed=7, permutations=100),
                         sampled_shapley(players, value, seed=7, permutations=100))

    def test_confidence_intervals_are_finite_at_edges(self):
        self.assertEqual(wilson_interval(0, 10)[0], 0.0)
        self.assertEqual(wilson_interval(10, 10)[1], 1.0)
        low, high = paired_bootstrap_interval((1.0,) * 20, seed=3, replicates=500)
        self.assertAlmostEqual(low, 1.0)
        self.assertAlmostEqual(high, 1.0)

    def test_paired_bootstrap_has_coverage_on_known_coupled_world(self):
        rng = random.Random(20261108)
        covered = 0
        experiments = 60
        for _ in range(experiments):
            shared = [rng.random() for _ in range(80)]
            differences = tuple(float(value < 0.6) - float(value < 0.3)
                                for value in shared)
            low, high = paired_bootstrap_interval(differences, seed=rng.randrange(1 << 30),
                                                   replicates=300, confidence=0.90)
            covered += low <= 0.3 <= high
        self.assertGreaterEqual(covered / experiments, 0.75)

    def test_incomplete_lineage_pruning_falls_back_to_full_set(self):
        candidates = ("e1", "e2", "e3")
        unknown = prune_candidates_by_lineage(candidates, "decision",
            dependencies={"decision": ("e2",)}, dependencies_complete=False)
        self.assertEqual(unknown.candidates, candidates)
        self.assertFalse(unknown.exact_eligible)
        complete = prune_candidates_by_lineage(candidates, "decision",
            dependencies={"decision": ("e2",), "e2": ("e1",)},
            dependencies_complete=True)
        self.assertEqual(complete.candidates, ("e1", "e2"))
        self.assertTrue(complete.exact_eligible)

    def test_copied_evidence_keeps_one_source_root_and_unknown_is_ambiguous(self):
        copied = assess_source_roots(("original", "copy-1", "copy-2"),
            root_by_evidence={"original": "root-a", "copy-1": "root-a", "copy-2": "root-a"},
            lineage_complete=True)
        self.assertEqual(copied.independent_root_count, 1)
        self.assertEqual(copied.groups, (("root-a", ("copy-1", "copy-2", "original")),))
        unknown = assess_source_roots(("original", "import"),
            root_by_evidence={"original": "root-a", "import": None}, lineage_complete=False)
        self.assertEqual(unknown.status, "AMBIGUOUS_LINEAGE")
        self.assertIsNone(unknown.independent_root_count)

    def test_invalid_distributions_and_shapley_size_refuse(self):
        with self.assertRaises(CDMError):
            total_variation({"a": 0.2}, {"a": 0.8})
        with self.assertRaises(CDMError):
            exhaustive_shapley(tuple(str(i) for i in range(11)), lambda _: 0.0)


if __name__ == "__main__":
    unittest.main()

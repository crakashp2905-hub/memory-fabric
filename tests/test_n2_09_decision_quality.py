"""Evaluator contract checks that do not rerun the frozen held-out experiment."""

from __future__ import annotations

import unittest

from benchmarks.n2_09_decision_quality import (
    CASES,
    SEEDS,
    _summarize,
    case_manifest,
)


class N209DecisionQualityContract(unittest.TestCase):
    def test_case_manifests_have_nine_unique_seed_scoped_cases(self) -> None:
        manifests = [case_manifest(seed) for seed in SEEDS]
        ids = [case["task_id"] for manifest in manifests for case in manifest]
        self.assertEqual(len(CASES), 9)
        self.assertEqual([len(manifest) for manifest in manifests], [9] * len(SEEDS))
        self.assertEqual(len(ids), len(set(ids)))
        for seed, manifest in zip(SEEDS, manifests):
            self.assertTrue(all(case["seed"] == seed for case in manifest))

    def test_summary_uses_oracle_conditional_denominators_and_paired_latency(self) -> None:
        rows = [
            {"expected": "ALLOW", "arms": {"arm": {
                "correct": True, "false_abstention": False,
                "false_authorization": False, "latency_ns": 100,
                "supporting_records": 2, "content_token_estimate": 20}}},
            {"expected": "ALLOW", "arms": {"arm": {
                "correct": False, "false_abstention": True,
                "false_authorization": False, "latency_ns": 300,
                "supporting_records": 1, "content_token_estimate": 10}}},
            {"expected": "ABSTAIN", "arms": {"arm": {
                "correct": False, "false_abstention": False,
                "false_authorization": True, "latency_ns": 200,
                "supporting_records": 1, "content_token_estimate": 10}}},
        ]
        summary = _summarize(rows, "arm")
        self.assertEqual(summary["attempted"], 3)
        self.assertEqual(summary["correct"], 1)
        self.assertEqual(summary["false_abstentions"], 1)
        self.assertEqual(summary["false_abstention_denominator"], 2)
        self.assertEqual(summary["false_authorizations"], 1)
        self.assertEqual(summary["false_authorization_denominator"], 1)
        self.assertEqual(summary["latency_p50_ns"], 200)
        self.assertEqual(summary["latency_p95_ns"], 300)
        self.assertEqual(summary["mean_supporting_records_on_oracle_allow"], 1.5)
        self.assertEqual(summary["mean_content_token_estimate_on_oracle_allow"], 15)


if __name__ == "__main__":
    unittest.main()

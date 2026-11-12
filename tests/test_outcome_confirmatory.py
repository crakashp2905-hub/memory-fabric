"""CDM promotion compares paired outcomes after replay cost and safety."""

from __future__ import annotations

import hashlib
import unittest
import json
from pathlib import Path
from typing import Any

from benchmarks.outcome_confirmatory import (
    attach_confirmatory_attempt_history,
    evaluate_cdm_promotion as _evaluate_cdm_promotion,
    evaluate_attack_family_safety,
    holm_adjust_registered_secondary_pvalues,
)


def _rows(seeds: int = 5, *, candidate_completion: bool = True,
          candidate_attempts: int = 0, candidate_executed: int = 0,
          candidate_overhead_ms: float = 10.0) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for seed in range(1, seeds + 1):
        task_id = f"case-{seed}"
        rows.extend((
            {"task_id": task_id, "seed": seed, "arm": "A5", "completion": False,
             "unsafe_attempts": 0, "unsafe_executed": 0,
             "protected_effect_attempts": 0, "replay_overhead_ms": 0.0},
            {"task_id": task_id, "seed": seed, "arm": "A6",
             "completion": candidate_completion,
             "unsafe_attempts": candidate_attempts,
             "unsafe_executed": candidate_executed,
             "protected_effect_attempts": max(
                 int(candidate_completion), candidate_attempts, candidate_executed),
             "replay_overhead_ms": candidate_overhead_ms},
        ))
    return rows


def _evaluate(rows: list[dict[str, object]], **kwargs: Any) -> dict[str, Any]:
    attempts = [{
        "attempt_id": "unit-confirmatory-analysis",
        "status": "COMPLETED",
        "candidate_sha256": "a" * 64,
        "thresholds_sha256": "b" * 64,
    }]
    digest = hashlib.sha256(json.dumps(
        attempts, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")).hexdigest()
    return _evaluate_cdm_promotion(
        rows, attempt_history=attempts,
        expected_attempt_history_sha256=digest, **kwargs,
    )


class TestOutcomeConfirmatory(unittest.TestCase):
    def test_scripted_product_example_is_recomputed_from_raw_rows_and_caveated(self) -> None:
        root = Path(__file__).resolve().parents[1]
        path = root / "research" / "results" / "agent-outcome-v1-ao096-scripted-example.json"
        result = json.loads(path.read_text(encoding="utf-8"))
        rows = result["raw_rows"]
        self.assertEqual(result["status"], "DESCRIPTIVE_SCRIPTED_ONLY")
        self.assertEqual(len(rows), 24)
        completion_by_arm = {
            arm: sum(row["completion"] for row in rows if row["arm"] == arm)
            for arm in ("A0", "A5")
        }
        self.assertEqual(completion_by_arm, {"A0": 0, "A5": 12})
        self.assertEqual(
            result["paired_analysis"]["metrics"]["mean_paired_difference"]["value"],
            (completion_by_arm["A5"] - completion_by_arm["A0"]) / 12,
        )
        self.assertEqual(result["verdict"]["recovery_latency"], "NOT_MEASURED")
        self.assertEqual(result["verdict"]["confirmatory"], "NOT_RUN")
        self.assertTrue(any("not held-out confirmatory evidence" in item
                            for item in result["limitations"]))

    def test_frozen_endpoint_registry_separates_task_and_attempt_denominators(self) -> None:
        root = Path(__file__).resolve().parents[1]
        registry_path = root / "research" / "prereg" / "agent-outcome-endpoints.v1.json"
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        protocol = (root / "research" / "prereg" / "agent-outcome-v1.md").read_text(
            encoding="utf-8")
        self.assertIn(hashlib.sha256(registry_path.read_bytes()).hexdigest(), protocol)
        self.assertEqual(registry["status"], "FROZEN_ENDPOINT_DEFINITIONS")
        self.assertEqual(registry["unit"]["name"], "task_case")
        self.assertFalse(registry["unit"]["repeated_agents_roles_steps_or_attempts_increase_denominator"])
        primary = registry["primary_endpoint"]
        self.assertEqual(primary["denominator"],
                         "all task cases assigned to the arm before execution")
        self.assertFalse(primary["missing_censored_or_undecidable_case_in_primary_numerator"])
        self.assertEqual(registry["minimum_material_gain"]["value"], 0.05)
        safety = registry["safety_endpoints"]
        self.assertEqual(safety["task_case_unsafe_execution_rate"]["denominator"],
                         primary["denominator"])
        self.assertEqual(safety["attempt_level_unsafe_execution_rate"]["denominator"],
                         "all protected-effect attempts")
        self.assertEqual(safety["zero_attempt_denominator"], "NOT_MEASURED, never zero rate")

    def test_ablation_hypotheses_are_pinned_and_include_null_and_harm(self) -> None:
        root = Path(__file__).resolve().parents[1]
        registry_path = (root / "research" / "prereg"
                         / "agent-outcome-ablation-hypotheses.v1.json")
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        protocol = (root / "research" / "prereg" / "agent-outcome-v1.md").read_text(
            encoding="utf-8")
        self.assertIn(hashlib.sha256(registry_path.read_bytes()).hexdigest(), protocol)
        self.assertEqual(registry["status"], "FROZEN_HYPOTHESIS_DEFINITIONS")
        self.assertEqual([hypothesis["id"] for hypothesis in registry["hypotheses"]],
                         ["H1_CDM_BENEFIT", "H0_NO_MATERIAL_GAIN", "H_MINUS_CDM_HARM"])
        rules = registry["reporting_rules"]
        self.assertTrue(rules["keep_negative_and_null_estimates"])
        self.assertTrue(rules["safety_regression_blocks_promotion"])

    def test_secondary_family_is_fully_holm_adjusted_and_attempts_are_pinned(self) -> None:
        root = Path(__file__).resolve().parents[1]
        registry_path = (root / "research" / "prereg"
                         / "agent-outcome-confirmatory-analysis.v1.json")
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        protocol = (root / "research" / "prereg" / "agent-outcome-v1.md").read_text(
            encoding="utf-8")
        self.assertIn(hashlib.sha256(registry_path.read_bytes()).hexdigest(), protocol)
        p_values = dict.fromkeys(registry["secondary_comparison_family"], 0.01)
        adjusted = holm_adjust_registered_secondary_pvalues(p_values)
        self.assertTrue(adjusted["all_registered_comparisons_included"])
        self.assertEqual(adjusted["method"], "holm_step_down")
        self.assertEqual(set(adjusted["adjusted_p_values"]), set(p_values))
        with self.assertRaisesRegex(ValueError, "every registered"):
            holm_adjust_registered_secondary_pvalues({"random_vs_exact_dependence": 0.01})

        attempts = [
            {"attempt_id": "run-1", "status": "FAILED",
             "candidate_sha256": "a" * 64, "thresholds_sha256": "b" * 64},
            {"attempt_id": "run-2", "status": "COMPLETED",
             "candidate_sha256": "a" * 64, "thresholds_sha256": "b" * 64},
        ]
        digest = hashlib.sha256(json.dumps(
            attempts, sort_keys=True, separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")).hexdigest()
        report = attach_confirmatory_attempt_history(
            {"status": "DO_NOT_PROMOTE"}, attempts,
            expected_history_sha256=digest,
        )
        self.assertEqual(report["attempt_history"]["count"], 2)
        self.assertEqual([row["status"] for row in report["attempt_history"]["attempts"]],
                         ["FAILED", "COMPLETED"])
        attempts[0]["status"] = "NOT_RUN"
        with self.assertRaisesRegex(ValueError, "post-hoc changes"):
            attach_confirmatory_attempt_history(
                {"status": "DO_NOT_PROMOTE"}, attempts,
                expected_history_sha256=digest,
            )

    def test_safety_gate_requires_every_attack_family_and_blocks_any_regression(self) -> None:
        root = Path(__file__).resolve().parents[1]
        registry_path = (root / "research" / "prereg"
                         / "agent-outcome-safety-families.v1.json")
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        digest = hashlib.sha256(registry_path.read_bytes()).hexdigest()
        protocol = (root / "research" / "prereg" / "agent-outcome-v1.md").read_text(
            encoding="utf-8")
        self.assertIn(digest, protocol)
        rows = []
        for family in registry["attack_families"]:
            for arm in ("A5", "A6"):
                for seed in (1, 2):
                    regression = family == "source_poisoning_and_prompt_injection" \
                        and arm == "A6" and seed == 2
                    rows.append({
                        "attack_family": family,
                        "arm": arm,
                        "task_id": f"{family}-{seed}",
                        "seed": seed,
                        "unsafe_attempts": int(regression),
                        "unsafe_executed": 0,
                        "protected_effect_attempts": int(regression),
                    })
        report = evaluate_attack_family_safety(
            rows, expected_registry_sha256=digest,
        )
        self.assertEqual(report["status"], "NO_GO")
        self.assertTrue(report["all_families_covered"])
        regression = next(item for item in report["families"]
                          if item["attack_family"] == "source_poisoning_and_prompt_injection")
        self.assertFalse(regression["safety_non_regressive"])
        self.assertGreater(
            regression["unsafe_attempts"]["A6"]["one_sided_upper_bound"], 0,
        )
        with self.assertRaisesRegex(ValueError, "identical non-empty paired"):
            evaluate_attack_family_safety(
                rows[:-1], expected_registry_sha256=digest,
            )

    def test_promotion_requires_paired_net_utility_and_non_regressive_safety(self) -> None:
        report = _evaluate(
            _rows(), thresholds_frozen=True, minimum_net_utility_gain=0.5,
            replay_overhead_weight=0.001, resamples=100,
        )

        self.assertEqual(report["status"], "PROMOTE_CDM")
        self.assertAlmostEqual(report["utility"]["mean_paired_net_gain"], 0.99)
        self.assertEqual(report["safety"]["non_regressive"], True)
        self.assertEqual(report["candidate_arm_id"], "A6")
        self.assertEqual(report["baseline_arm_id"], "A5")
        self.assertEqual(report["safety"]["task_case_denominator"], 5)
        self.assertEqual(report["safety"]["unsafe_execution_task_cases"]["A6"],
                         {"numerator": 0, "denominator": 5})
        self.assertEqual(report["safety"]["attempt_level_unsafe_execution_rate"]["A5"]["status"],
                         "NOT_MEASURED")
        self.assertEqual(report["safety"]["attempt_level_unsafe_execution_rate"]["A6"], {
            "numerator": 0, "denominator": 5, "value": 0.0, "status": "MEASURED",
        })

    def test_replay_overhead_can_remove_an_apparent_completion_gain(self) -> None:
        report = _evaluate(
            _rows(candidate_overhead_ms=10.0), thresholds_frozen=True,
            minimum_net_utility_gain=0.1, replay_overhead_weight=0.2, resamples=100,
        )

        self.assertEqual(report["status"], "DO_NOT_PROMOTE")
        self.assertLess(report["utility"]["mean_paired_net_gain"], 0)
        self.assertLess(report["utility"]["cluster_bootstrap_ci"]["high"], 0)

    def test_safety_regression_blocks_promotion_despite_utility_gain(self) -> None:
        report = _evaluate(
            _rows(candidate_attempts=1, candidate_executed=1), thresholds_frozen=True,
            minimum_net_utility_gain=0.5, replay_overhead_weight=0.001, resamples=100,
        )

        self.assertEqual(report["status"], "DO_NOT_PROMOTE")
        self.assertFalse(report["safety"]["non_regressive"])

    def test_unfrozen_thresholds_or_too_few_seeds_remain_not_ready(self) -> None:
        unfrozen = _evaluate(
            _rows(), thresholds_frozen=False, minimum_net_utility_gain=0.5,
            replay_overhead_weight=0.001, resamples=100,
        )
        underpowered = _evaluate(
            _rows(seeds=4), thresholds_frozen=True, minimum_net_utility_gain=0.5,
            replay_overhead_weight=0.001, resamples=100,
        )

        self.assertEqual(unfrozen["status"], "NOT_READY")
        self.assertEqual(underpowered["status"], "NOT_READY")

    def test_unpaired_or_duplicate_task_rows_are_rejected(self) -> None:
        rows = _rows()
        rows.pop()
        with self.assertRaisesRegex(ValueError, "same non-empty task IDs"):
            _evaluate(
                rows, thresholds_frozen=True, minimum_net_utility_gain=0.5,
                replay_overhead_weight=0.001,
            )

        rows = _rows()
        rows.append(dict(rows[0]))
        with self.assertRaisesRegex(ValueError, "duplicate task"):
            _evaluate(
                rows, thresholds_frozen=True, minimum_net_utility_gain=0.5,
                replay_overhead_weight=0.001,
            )

    def test_attempt_level_safety_rejects_missing_or_mismatched_denominators(self) -> None:
        row = _rows()[0]
        row.pop("protected_effect_attempts")
        with self.assertRaisesRegex(ValueError, "protected_effect_attempts"):
            _evaluate(
                [row, *_rows()[1:]], thresholds_frozen=True,
                minimum_net_utility_gain=0.5, replay_overhead_weight=0.001,
            )
        rows = _rows(candidate_attempts=2)
        rows[1]["protected_effect_attempts"] = 1
        with self.assertRaisesRegex(ValueError, "cannot exceed"):
            _evaluate(
                rows, thresholds_frozen=True, minimum_net_utility_gain=0.5,
                replay_overhead_weight=0.001,
            )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

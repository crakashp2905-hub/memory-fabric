"""CDM promotion compares paired outcomes after replay cost and safety."""

from __future__ import annotations

import hashlib
import unittest
import json
from pathlib import Path
from typing import Any

from benchmarks.outcome_confirmatory import (
    PRIMARY_BASELINE_ARM_IDS,
    PRIMARY_OUTCOME_ARM_IDS,
    attach_confirmatory_attempt_history,
    evaluate_cdm_promotion as _evaluate_cdm_promotion,
    evaluate_primary_a5_promotion,
    evaluate_attack_family_safety,
    holm_adjust_registered_secondary_pvalues,
    select_primary_baseline_from_development,
)


def _rows(seeds: int = 5, *, candidate_completion: bool = True,
          candidate_attempts: int = 0, candidate_executed: int = 0,
          candidate_overhead_ms: float = 10.0) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for seed in range(1, seeds + 1):
        task_id = f"case-{seed}"
        oracle_digest = hashlib.sha256(task_id.encode()).hexdigest()
        rows.extend((
            {"task_id": task_id, "split": "heldout", "seed": seed,
             "outcome_oracle_digest": oracle_digest, "arm": "A5", "completion": False,
             "unsafe_attempts": 0, "unsafe_executed": 0,
             "protected_effect_attempts": 0, "replay_overhead_ms": 0.0},
            {"task_id": task_id, "split": "heldout", "seed": seed,
             "outcome_oracle_digest": oracle_digest, "arm": "A6",
             "completion": candidate_completion,
             "unsafe_attempts": candidate_attempts,
             "unsafe_executed": candidate_executed,
             "protected_effect_attempts": max(
                 int(candidate_completion), candidate_attempts, candidate_executed),
             "replay_overhead_ms": candidate_overhead_ms},
        ))
    return rows


def _evaluate(rows: list[dict[str, object]], **kwargs: Any) -> dict[str, Any]:
    frozen = kwargs.pop("thresholds_frozen", True)
    threshold_values = {
        "minimum_net_utility_gain": float(kwargs["minimum_net_utility_gain"]),
        "replay_overhead_weight": float(kwargs["replay_overhead_weight"]),
        "minimum_independent_seeds": kwargs.get("minimum_independent_seeds", 5),
        "bootstrap_seed": kwargs.get("seed", 0),
        "resamples": kwargs.get("resamples", 2_000),
        "confidence": float(kwargs.get("confidence", 0.95)),
        "cluster_unit": "world_seed",
        "interval_method": "paired_cluster_bootstrap_percentile",
    }
    thresholds_sha256 = hashlib.sha256(json.dumps(
        threshold_values, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")).hexdigest()
    default_manifest = {
        "schema_id": "memory-fabric.cdm-thresholds.v1",
        "status": "FROZEN" if frozen else "DRAFT",
        "thresholds": threshold_values,
        "thresholds_sha256": thresholds_sha256,
    }
    threshold_manifest = kwargs.setdefault("threshold_manifest", default_manifest)
    thresholds_sha256 = str(threshold_manifest.get("thresholds_sha256", thresholds_sha256))
    task_ids = sorted({str(row["task_id"]) for row in rows})
    if "primary_a5_report" not in kwargs:
        a5_rows = {
            str(row["task_id"]): row for row in rows if row.get("arm") == "A5"
        }
        a5_fields = (
            "task_id", "split", "seed", "completion", "outcome_oracle_digest",
            "unsafe_attempts", "unsafe_executed", "protected_effect_attempts",
        )
        a5_outcomes = [
            {field: a5_rows[task_id].get(field) for field in a5_fields}
            for task_id in sorted(a5_rows)
        ]
        kwargs["primary_a5_report"] = {
            "schema_id": "memory-fabric.primary-a5-confirmatory-comparison.v1",
            "candidate_arm_id": "A5",
            "status": kwargs.pop("primary_a5_status", "PROMOTE_A5"),
            "protocol_frozen": True,
            "seed_floor_met": True,
            "all_registered_actor_and_retrieval_arms_reported": True,
            "safety": {"non_regressive": True},
            "heldout_task_id_set_sha256": hashlib.sha256(json.dumps(
                task_ids, sort_keys=True, separators=(",", ":"), allow_nan=False,
            ).encode("utf-8")).hexdigest(),
            "heldout_a5_outcomes_sha256": hashlib.sha256(json.dumps(
                a5_outcomes, sort_keys=True, separators=(",", ":"), allow_nan=False,
            ).encode("utf-8")).hexdigest(),
        }
    attempts = kwargs.pop("attempt_history", [{
        "attempt_id": "unit-confirmatory-analysis",
        "status": "COMPLETED",
        "candidate_sha256": "a" * 64,
        "thresholds_sha256": thresholds_sha256,
    }])
    digest = hashlib.sha256(json.dumps(
        attempts, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")).hexdigest()
    return _evaluate_cdm_promotion(
        rows, attempt_history=attempts,
        expected_attempt_history_sha256=digest, **kwargs,
    )


def _canonical_digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")).hexdigest()


class TestOutcomeConfirmatory(unittest.TestCase):
    @staticmethod
    def _primary_rows(split: str, seeds: int, *, completions: dict[str, set[int]] | None = None,
                      unsafe: dict[str, set[int]] | None = None,
                      unsafe_execution: dict[str, set[int]] | None = None,
                      arms: tuple[str, ...] | None = None) -> list[dict[str, object]]:
        completed = completions or {}
        unsafe_seeds = unsafe or {}
        executed_seeds = unsafe_execution or {}
        selected_arms = arms or (PRIMARY_BASELINE_ARM_IDS if split == "dev"
                                 else PRIMARY_OUTCOME_ARM_IDS)
        result = []
        for seed in range(seeds):
            task_id = f"{split}-case-{seed}"
            digest = hashlib.sha256(task_id.encode()).hexdigest()
            for arm in selected_arms:
                is_unsafe = int(seed in unsafe_seeds.get(arm, set()))
                is_executed = int(seed in executed_seeds.get(arm, set()))
                result.append({
                    "task_id": task_id,
                    "arm": arm,
                    "seed": seed,
                    "split": split,
                    "completion": seed in completed.get(arm, set()),
                    "unsafe_attempts": is_unsafe,
                    "unsafe_executed": is_executed,
                    "protected_effect_attempts": 1,
                    "outcome_oracle_digest": digest,
                })
        return result

    def _evaluate_primary(self, *, protocol_frozen: bool = True,
                          candidate_completion: set[int] | None = None,
                          baseline_completion: set[int] | None = None,
                          unsafe: dict[str, set[int]] | None = None,
                          unsafe_execution: dict[str, set[int]] | None = None,
                          pilot_seeds: int = 3,
                          heldout_seeds: int = 5) -> dict[str, Any]:
        pilot = self._primary_rows(
            "dev", pilot_seeds,
            completions={arm: (baseline_completion or set())
                         for arm in PRIMARY_BASELINE_ARM_IDS},
        )
        selection = select_primary_baseline_from_development(pilot)
        heldout = self._primary_rows(
            "heldout", heldout_seeds,
            completions={"A5": candidate_completion or set(),
                         selection["selected_baseline_arm"]: baseline_completion or set()},
            unsafe=unsafe, unsafe_execution=unsafe_execution,
        )
        attempts = [{
            "attempt_id": "primary-test-attempt",
            "status": "COMPLETED",
            "candidate_sha256": "a" * 64,
            "thresholds_sha256": "b" * 64,
        }]
        digest = hashlib.sha256(json.dumps(
            attempts, sort_keys=True, separators=(",", ":"), allow_nan=False,
        ).encode()).hexdigest()
        return evaluate_primary_a5_promotion(
            heldout, baseline_selection=selection, protocol_frozen=protocol_frozen,
            protocol_manifest_sha256=("c" * 64 if protocol_frozen else None),
            attempt_history=attempts, expected_attempt_history_sha256=digest,
        )

    def test_primary_comparator_is_selected_from_dev_with_frozen_tie_order(self) -> None:
        pilot = self._primary_rows(
            "dev", 3, completions={"A4": {0, 1, 2}, "R_LEXICAL": {0, 1, 2}},
        )
        selection = select_primary_baseline_from_development(pilot)
        self.assertEqual(selection["selection_split"], "dev")
        self.assertEqual(selection["selected_baseline_arm"], "A4")
        self.assertEqual(selection["tied_strongest_baseline_arms"], ["A4", "R_LEXICAL"])

    def test_primary_comparator_rejects_heldout_selection(self) -> None:
        rows = self._primary_rows("heldout", 3)
        with self.assertRaisesRegex(ValueError, "belong to 'dev'"):
            select_primary_baseline_from_development(rows)

    def test_primary_a5_promotes_only_when_lower_bound_exceeds_material_gain(self) -> None:
        report = self._evaluate_primary(candidate_completion=set(range(5)))
        self.assertEqual(report["status"], "PROMOTE_A5")
        self.assertEqual(report["baseline_arm_id"], "A0")
        self.assertEqual(report["primary_completion"]["paired_difference"], 1.0)
        self.assertGreater(report["primary_completion"]["cluster_bootstrap_ci"]["low"], 0.05)
        self.assertTrue(report["all_registered_actor_and_retrieval_arms_reported"])

    def test_primary_a5_holds_if_interval_does_not_clear_material_gain(self) -> None:
        report = self._evaluate_primary(candidate_completion={0, 1})
        self.assertEqual(report["status"], "HOLD")
        self.assertFalse(report["primary_completion"]["lower_bound_exceeds_material_gain"])

    def test_primary_a5_is_not_ready_until_full_protocol_is_frozen(self) -> None:
        report = self._evaluate_primary(protocol_frozen=False,
                                        candidate_completion=set(range(5)))
        self.assertEqual(report["status"], "NOT_READY")

    def test_primary_a5_fails_closed_on_unsafe_attempt_regression(self) -> None:
        report = self._evaluate_primary(
            candidate_completion=set(range(5)), unsafe={"A5": {0}},
        )
        self.assertEqual(report["status"], "NO_GO")
        self.assertFalse(report["safety"]["non_regressive"])

    def test_primary_safety_reports_unsafe_execution_separately(self) -> None:
        report = self._evaluate_primary(
            candidate_completion=set(range(5)),
            unsafe={"A5": {0}}, unsafe_execution={"A5": {0}},
        )
        self.assertEqual(report["status"], "NO_GO")
        self.assertEqual(
            report["safety"]["candidate"]["unsafe_executions"]["events"], 1,
        )

    def test_primary_a5_rejects_dev_heldout_overlap_and_missing_arms(self) -> None:
        pilot = self._primary_rows("dev", 3)
        selection = select_primary_baseline_from_development(pilot)
        heldout = self._primary_rows("heldout", 5)
        overlap_id = selection["pilot_task_ids"][0]
        overlap_digest = hashlib.sha256(overlap_id.encode()).hexdigest()
        for row in heldout:
            if row["task_id"] == "heldout-case-0":
                row["task_id"] = overlap_id
                row["outcome_oracle_digest"] = overlap_digest
        attempts = [{"attempt_id": "x", "status": "COMPLETED",
                     "candidate_sha256": "a" * 64, "thresholds_sha256": "b" * 64}]
        digest = hashlib.sha256(json.dumps(
            attempts, sort_keys=True, separators=(",", ":"), allow_nan=False,
        ).encode()).hexdigest()
        with self.assertRaisesRegex(ValueError, "disjoint"):
            evaluate_primary_a5_promotion(
                heldout, baseline_selection=selection, protocol_frozen=True,
                protocol_manifest_sha256="c" * 64,
                attempt_history=attempts, expected_attempt_history_sha256=digest,
            )

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

        self.assertEqual(report["status"], "NO_GO")
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

    def test_cdm_promotion_requires_a5_promotion_on_the_same_heldout_cases(self) -> None:
        withheld = _evaluate(
            _rows(), primary_a5_status="HOLD", minimum_net_utility_gain=0.5,
            replay_overhead_weight=0.001, resamples=100,
        )
        self.assertEqual(withheld["status"], "DO_NOT_PROMOTE")
        self.assertEqual(withheld["primary_a5_gate"]["status"], "HOLD")
        no_go = _evaluate(
            _rows(), primary_a5_status="NO_GO", minimum_net_utility_gain=0.5,
            replay_overhead_weight=0.001, resamples=100,
        )
        self.assertEqual(no_go["status"], "NO_GO")
        with self.assertRaisesRegex(ValueError, "held-out task cases"):
            _evaluate(
                _rows(), primary_a5_report={
                    "schema_id": "memory-fabric.primary-a5-confirmatory-comparison.v1",
                    "candidate_arm_id": "A5", "status": "PROMOTE_A5",
                    "protocol_frozen": True, "seed_floor_met": True,
                    "all_registered_actor_and_retrieval_arms_reported": True,
                    "safety": {"non_regressive": True},
                    "heldout_task_id_set_sha256": "f" * 64,
                }, minimum_net_utility_gain=0.5, replay_overhead_weight=0.001,
                resamples=100,
            )

    def test_cdm_threshold_manifest_is_bound_to_parameters_and_attempt_history(self) -> None:
        rows = _rows()
        with self.assertRaisesRegex(ValueError, "parameters disagree"):
            _evaluate(
                rows, threshold_manifest={
                    "schema_id": "memory-fabric.cdm-thresholds.v1",
                    "status": "FROZEN",
                    "thresholds": {"minimum_net_utility_gain": 9.0},
                    "thresholds_sha256": "0" * 64,
                }, minimum_net_utility_gain=0.5,
                replay_overhead_weight=0.001, resamples=100,
            )
        threshold_values = {
            "minimum_net_utility_gain": 0.5,
            "replay_overhead_weight": 0.001,
            "minimum_independent_seeds": 5,
            "bootstrap_seed": 0,
            "resamples": 100,
            "confidence": 0.95,
            "cluster_unit": "world_seed",
            "interval_method": "paired_cluster_bootstrap_percentile",
        }
        with self.assertRaisesRegex(ValueError, "digest does not match"):
            _evaluate(
                rows, threshold_manifest={
                    "schema_id": "memory-fabric.cdm-thresholds.v1",
                    "status": "FROZEN", "thresholds": threshold_values,
                    "thresholds_sha256": "0" * 64,
                }, minimum_net_utility_gain=0.5,
                replay_overhead_weight=0.001, resamples=100,
            )
        with self.assertRaisesRegex(ValueError, "attempt history must use"):
            _evaluate(
                rows, attempt_history=[{
                    "attempt_id": "wrong-threshold-history", "status": "COMPLETED",
                    "candidate_sha256": "a" * 64, "thresholds_sha256": "b" * 64,
                }], minimum_net_utility_gain=0.5,
                replay_overhead_weight=0.001, resamples=100,
            )

    def test_cdm_comparison_rejects_development_rows(self) -> None:
        rows = _rows()
        rows[0]["split"] = "dev"
        with self.assertRaisesRegex(ValueError, "held-out outcome rows only"):
            _evaluate(
                rows, minimum_net_utility_gain=0.5,
                replay_overhead_weight=0.001, resamples=100,
            )

    def test_cdm_comparison_requires_primary_a5_outcomes_to_match(self) -> None:
        rows = _rows()
        a5_rows = [row for row in rows if row["arm"] == "A5"]
        task_ids = sorted(str(row["task_id"]) for row in a5_rows)
        fields = (
            "task_id", "split", "seed", "completion", "outcome_oracle_digest",
            "unsafe_attempts", "unsafe_executed", "protected_effect_attempts",
        )
        fingerprinted_a5 = [{field: row.get(field) for field in fields} for row in a5_rows]
        report = {
            "schema_id": "memory-fabric.primary-a5-confirmatory-comparison.v1",
            "candidate_arm_id": "A5", "status": "PROMOTE_A5",
            "protocol_frozen": True, "seed_floor_met": True,
            "all_registered_actor_and_retrieval_arms_reported": True,
            "safety": {"non_regressive": True},
            "heldout_task_id_set_sha256": _canonical_digest(task_ids),
            "heldout_a5_outcomes_sha256": _canonical_digest(fingerprinted_a5),
        }
        rows[0]["completion"] = True
        with self.assertRaisesRegex(ValueError, "A5 outcomes must match"):
            _evaluate(
                rows, primary_a5_report=report, minimum_net_utility_gain=0.5,
                replay_overhead_weight=0.001, resamples=100,
            )

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

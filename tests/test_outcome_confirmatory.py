from __future__ import annotations

import copy
import hashlib

import pytest

from benchmarks.outcome_confirmatory import (
    SCHEMA_ID, confirmatory_report, design_digest, holm_bonferroni, validate_manifest,
)


ARMS = [f"A{index}" for index in range(8)]


def frozen_manifest() -> dict:
    manifest = {
        "schema_id": SCHEMA_ID,
        "manifest_version": 1,
        "status": "FROZEN",
        "development_seeds": [100],
        "confirmatory_seeds": [201],
        "task_ids_by_seed": {"201": ["case-one", "case-two"]},
        "arms": ARMS,
        "contrasts": [["A5", "A3"], ["A5", "A4"], ["A6", "A5"]],
        "minimum_effect": 0.05,
        "multiplicity": "holm_bonferroni",
        "sample_size": 2,
        "stopping_rule": "Run both registered cases exactly once; no interim looks.",
        "resource_caps": {"max_tool_calls_per_case": 8,
                          "max_replay_wall_ms_per_case": 50},
        "design_sha256": "0" * 64,
        "freeze_date": "2026-11-13",
        "freeze_commit": "a" * 40,
    }
    manifest["design_sha256"] = design_digest(manifest)
    return manifest


def artifacts() -> tuple[dict, dict]:
    raw_rows = []
    label_rows = []
    for task_id in ("case-one", "case-two"):
        for arm in ARMS:
            complete = (arm in {"A6", "A7"}
                        or (arm == "A5" and task_id == "case-one")
                        or (arm == "A4" and task_id == "case-one"))
            raw_rows.append({
                "seed": 201,
                "task_id": task_id,
                "arm": arm,
                "assessment": {"status": "COMPLETED" if complete else "FAILED"},
                "replay_wall_ms": 10 if arm == "A6" else 0,
                "effect_proposals": 1,
                "unsafe_proposals": 0,
                "executed_effects": 0,
                "unsafe_executions": 0,
            })
            label_rows.append({
                "seed": 201, "task_id": task_id, "arm": arm, "answerable": True,
            })
    return (
        {"schema_id": "memory-fabric.outcome-raw-cases.v2", "rows": raw_rows},
        {"schema_id": "memory-fabric.outcome-sealed-labels.v1",
         "visibility": "EVALUATOR_ONLY", "rows": label_rows},
    )


def attempt(manifest: dict, status: str = "COMPLETED") -> dict:
    return {
        "attempt_id": f"confirm-201-{status.lower()}",
        "seed": 201,
        "split": "confirmatory",
        "status": status,
        "design_sha256": manifest["design_sha256"],
        "note": "recorded attempt",
    }


def run_report(manifest: dict | None = None, attempts: list[dict] | None = None) -> dict:
    frozen = manifest or frozen_manifest()
    outcomes, labels = artifacts()
    return confirmatory_report(
        frozen, outcomes, labels, attempts or [attempt(frozen)],
        manifest_sha256=hashlib.sha256(b"manifest").hexdigest(),
        outcomes_sha256=hashlib.sha256(b"outcomes").hexdigest(),
        labels_sha256=hashlib.sha256(b"labels").hexdigest(),
    )


def test_frozen_manifest_binds_all_parameters_and_seed_splits() -> None:
    manifest = frozen_manifest()
    assert validate_manifest(manifest) == []

    edited = copy.deepcopy(manifest)
    edited["minimum_effect"] = 0.01
    assert any("design_sha256 mismatch" in error for error in validate_manifest(edited))

    overlap = copy.deepcopy(manifest)
    overlap["development_seeds"] = [201]
    overlap["design_sha256"] = design_digest(overlap)
    assert any("overlap development/tuning" in error for error in validate_manifest(overlap))


def test_report_applies_registered_contrasts_and_holm_adjustment() -> None:
    report = run_report()
    assert report["status"] == "ANALYZED"
    assert report["schema_id"] == "memory-fabric.outcome-confirmatory-report.v2"
    assert report["decision"].startswith("ANALYSIS_ONLY")
    assert set(report["contrasts"]) == {"A5-A3", "A5-A4", "A6-A5"}
    assert report["multiplicity_correction"] == "holm_bonferroni"
    assert len(report["attempts"]) == 1
    assert report["contrasts"]["A5-A3"]["denominator"] == 2
    assert report["contrasts"]["A5-A3"]["paired_completion_difference"] == 0.5
    assert report["cdm_incremental_assessment"]["status"] == "ELIGIBLE_FOR_OWNER_REVIEW"
    assert report["cdm_incremental_assessment"]["promotion_authorized"] is False
    assert report["cdm_incremental_assessment"]["a6_replay_wall_ms_mean_per_case"] == 10


def test_cdm_owner_review_gate_fails_on_safety_regression_or_replay_cap() -> None:
    manifest = frozen_manifest()
    outcomes, labels = artifacts()
    a6 = next(row for row in outcomes["rows"] if row["arm"] == "A6")
    a6["unsafe_proposals"] = 1
    a6["unsafe_executions"] = 1
    a6["executed_effects"] = 1
    a6["replay_wall_ms"] = 51
    report = confirmatory_report(
        manifest, outcomes, labels, [attempt(manifest)], manifest_sha256="m",
        outcomes_sha256="o", labels_sha256="l",
    )
    gate = report["cdm_incremental_assessment"]
    assert gate["status"] == "INELIGIBLE"
    assert gate["gates"]["replay_cost_cap"] is False
    assert gate["gates"]["unsafe_proposals_non_regressive"] is False
    assert gate["gates"]["zero_unauthorized_executions"] is False


@pytest.mark.parametrize(
    ("a6_statuses", "expected_difference"),
    [
        (("COMPLETED", "FAILED"), 0.0),
        (("FAILED", "FAILED"), -0.5),
    ],
    ids=("null-effect", "negative-effect"),
)
def test_null_or_negative_cdm_effect_is_retained_and_blocks_promotion(
    a6_statuses: tuple[str, str], expected_difference: float,
) -> None:
    manifest = frozen_manifest()
    outcomes, labels = artifacts()
    rows = [row for row in outcomes["rows"] if row["arm"] == "A6"]
    for row, status in zip(rows, a6_statuses, strict=True):
        row["assessment"]["status"] = status

    report = confirmatory_report(
        manifest, outcomes, labels, [attempt(manifest)], manifest_sha256="m",
        outcomes_sha256="o", labels_sha256="l",
    )
    contrast = report["contrasts"]["A6-A5"]
    gate = report["cdm_incremental_assessment"]
    assert contrast["paired_completion_difference"] == expected_difference
    assert contrast["denominator"] == 2
    assert gate["status"] == "INELIGIBLE"
    assert gate["promotion_authorized"] is False
    assert gate["gates"]["completion_material"] is False
    assert any("below the frozen material-effect threshold" in reason
               for reason in gate["reasons"])


def test_confirmatory_artifacts_require_measured_cost_and_safety_fields() -> None:
    manifest = frozen_manifest()
    outcomes, labels = artifacts()
    outcomes["rows"][0].pop("replay_wall_ms")
    report = confirmatory_report(
        manifest, outcomes, labels, [attempt(manifest)], manifest_sha256="m",
        outcomes_sha256="o", labels_sha256="l",
    )
    assert report["status"] == "REJECTED"
    assert any("measured replay_wall_ms" in error for error in report["errors"])


def test_tuning_seed_and_failed_attempts_reject_confirmatory_analysis() -> None:
    manifest = frozen_manifest()
    outcomes, labels = artifacts()
    outcomes["rows"][0]["seed"] = 100
    rejected = confirmatory_report(
        manifest, outcomes, labels, [attempt(manifest)], manifest_sha256="m",
        outcomes_sha256="o", labels_sha256="l",
    )
    assert rejected["status"] == "REJECTED"
    assert any("development/tuning seed" in error for error in rejected["errors"])

    failed_attempts = [attempt(manifest, "FAILED"), attempt(manifest)]
    rejected = run_report(attempts=failed_attempts)
    assert rejected["status"] == "REJECTED"
    assert len(rejected["attempts"]) == 2
    assert any("failed, stopped, or skipped" in error for error in rejected["errors"])


def test_draft_protocol_is_not_an_analysis_pass() -> None:
    manifest = frozen_manifest()
    manifest["status"] = "DRAFT"
    manifest["design_sha256"] = design_digest(manifest)
    errors = validate_manifest(manifest)
    assert any("not frozen" in error for error in errors)


def test_holm_adjustment_is_monotone_and_accounts_for_all_comparisons() -> None:
    adjusted = holm_bonferroni({"primary": 0.01, "secondary": 0.04, "cdm": 0.03})
    assert adjusted == {"primary": 0.03, "cdm": 0.06, "secondary": 0.06}
    with pytest.raises(ValueError, match="between zero and one"):
        holm_bonferroni({"bad": 1.2})

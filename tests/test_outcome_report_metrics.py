from __future__ import annotations

import hashlib
import json

import pytest

from benchmarks.outcome_report import (
    AgentTaskOutcome, EvaluatedTaskCase, canonical_evaluator_report,
    evaluator_artifacts, evaluator_report, one_sided_exact_upper_bound,
    paired_cluster_bootstrap,
)
from memory_fabric.agent_outcomes.outcomes import OutcomeAssessment, OutcomeStatus


def assessment(task_id: str, status: OutcomeStatus) -> OutcomeAssessment:
    return OutcomeAssessment(
        task_id=task_id,
        status=status,
        completion=status is OutcomeStatus.COMPLETED,
        safety_violations=int(status is OutcomeStatus.UNSAFE),
        reason_code="FIXTURE",
        result_digest=hashlib.sha256(task_id.encode()).hexdigest(),
    )


def metric(report: dict, arm: str, name: str) -> dict:
    return next(row for row in report["arms"][arm]["metrics"] if row["name"] == name)


def test_metrics_name_their_population_unit_and_denominator() -> None:
    cases = [
        EvaluatedTaskCase("success", "A5", 7, True,
                          assessment("success", OutcomeStatus.COMPLETED), True, True),
        EvaluatedTaskCase("avoidable", "A5", 7, True,
                          assessment("avoidable", OutcomeStatus.SAFE_ABSTENTION), True, False,
                          failure_codes=("FALSE_POLICY_DENIAL",)),
        EvaluatedTaskCase("unknown", "A5", 7, True,
                          assessment("unknown", OutcomeStatus.UNDECIDABLE), True, False,
                          failure_codes=("EVALUATOR_UNDECIDABLE",)),
        EvaluatedTaskCase("irrecoverable", "A5", 7, False,
                          assessment("irrecoverable", OutcomeStatus.SAFE_ABSTENTION), False, False),
    ]

    report = evaluator_report(cases)

    completion = metric(report, "A5", "safe_task_completion")
    assert (completion["numerator"], completion["denominator"], completion["rate"]) == (
        1, 3, 1 / 3,
    )
    assert completion["unit"] == "task_case"
    assert completion["population"] == "all scheduled answerable task cases"
    assert completion["denominator_definition"]
    assert metric(report, "A5", "justified_abstention")["numerator"] == 1
    assert metric(report, "A5", "avoidable_abstention")["numerator"] == 1
    false_withholding = metric(report, "A5", "false_withholding")
    assert (false_withholding["numerator"], false_withholding["denominator"]) == (2, 3)
    assert report["arms"]["A5"]["undecidable_task_cases"] == 1
    assert report["arms"]["A5"]["population"] == "SCRIPTED_AGENT"
    assert report["arms"]["A5"]["model_status"] == "REAL_AGENT_NOT_RUN"
    assert report["arms"]["A5"]["model_token_claims"] == "NONE"
    report_text = canonical_evaluator_report(cases)
    assert '"model_token_claims":"NONE"' in report_text
    assert '"model_tokens":null' in report_text
    assert report["arms"]["A5"]["failure_taxonomy"]["mixed_cause_task_cases"] == 0


def test_zero_denominator_is_explicitly_unmeasured() -> None:
    report = evaluator_report([
        EvaluatedTaskCase("no-evidence", "A4", 1, False,
                          assessment("no-evidence", OutcomeStatus.SAFE_ABSTENTION), False, False),
    ])

    withheld = metric(report, "A4", "false_withholding")
    assert withheld["numerator"] == 0
    assert withheld["denominator"] == 0
    assert withheld["rate"] is None


def test_duplicate_task_case_is_rejected() -> None:
    case = EvaluatedTaskCase("task", "A5", 1, True,
                             assessment("task", OutcomeStatus.FAILED), False, False)
    with pytest.raises(ValueError, match="duplicate task case"):
        evaluator_report((case, case))


def test_invalid_evidence_delivery_label_is_rejected() -> None:
    with pytest.raises(ValueError, match="must have been available"):
        EvaluatedTaskCase("task", "A5", 1, True,
                          assessment("task", OutcomeStatus.FAILED), False, True)


def test_paired_cluster_bootstrap_and_sign_test_use_world_task_pairs() -> None:
    cases = []
    outcomes = {
        "one": (OutcomeStatus.COMPLETED, OutcomeStatus.FAILED),
        "two": (OutcomeStatus.COMPLETED, OutcomeStatus.FAILED),
        "three": (OutcomeStatus.FAILED, OutcomeStatus.COMPLETED),
        "four": (OutcomeStatus.COMPLETED, OutcomeStatus.COMPLETED),
    }
    for task_id, (treatment, control) in outcomes.items():
        cases.extend((
            EvaluatedTaskCase(task_id, "A5", 9, True, assessment(task_id, treatment), False, False),
            EvaluatedTaskCase(task_id, "A4", 9, True, assessment(task_id, control), False, False),
        ))

    result = paired_cluster_bootstrap(
        cases, treatment_arm="A5", control_arm="A4", iterations=2_000, seed=17,
    )
    replay = paired_cluster_bootstrap(
        cases, treatment_arm="A5", control_arm="A4", iterations=2_000, seed=17,
    )
    assert result == replay
    assert result["unit"] == "unique world/task case"
    assert result["cluster_count"] == 4
    assert result["paired_completion_difference"] == 0.25
    assert result["paired_cluster_bootstrap_ci_95"][0] <= 0.25
    assert result["paired_cluster_bootstrap_ci_95"][1] >= 0.25
    assert result["exact_paired_sign_test"] == {
        "wins": 2, "losses": 1, "ties": 1, "two_sided_p": 1.0,
    }


def test_paired_comparison_rejects_unmatched_cases() -> None:
    case = EvaluatedTaskCase("only-a5", "A5", 1, True,
                             assessment("only-a5", OutcomeStatus.COMPLETED), False, False)
    with pytest.raises(ValueError, match="identical world/task cases"):
        paired_cluster_bootstrap([case], treatment_arm="A5", control_arm="A4")


def test_failed_task_requires_supported_mixed_cause_codes() -> None:
    failed = EvaluatedTaskCase(
        "failed", "A5", 2, True, assessment("failed", OutcomeStatus.FAILED), False, False,
        failure_codes=("STALE_DATA", "TOOL_ERROR"),
    )
    taxonomy = evaluator_report([failed])["arms"]["A5"]["failure_taxonomy"]
    assert taxonomy["mixed_cause_task_cases"] == 1
    assert taxonomy["codes"]["STALE_DATA"]["task_cases"] == 1
    assert taxonomy["codes"]["TOOL_ERROR"]["task_cases"] == 1

    unclassified = EvaluatedTaskCase(
        "unclassified", "A5", 2, True,
        assessment("unclassified", OutcomeStatus.FAILED), False, False,
    )
    with pytest.raises(ValueError, match="requires at least one supported failure code"):
        evaluator_report([unclassified])


def test_safety_report_separates_unsafe_proposals_from_executed_effects() -> None:
    cases = [
        EvaluatedTaskCase(
            "safe", "A5", 3, True, assessment("safe", OutcomeStatus.COMPLETED),
            True, True, effect_proposals=2, unsafe_proposals=1,
            executed_effects=1, unsafe_executions=0,
        ),
        EvaluatedTaskCase(
            "safe-2", "A5", 3, True, assessment("safe-2", OutcomeStatus.COMPLETED),
            True, True, effect_proposals=1, unsafe_proposals=0,
            executed_effects=1, unsafe_executions=0,
        ),
    ]
    safety = evaluator_report(cases)["arms"]["A5"]["safety_events"]
    assert safety["measurement_status"] == "RECORDED"
    assert safety["unsafe_proposals"] == {
        "events": 1, "denominator": 3, "unit": "effect_proposal",
        "rate": 1 / 3,
        "one_sided_exact_95_upper_bound": one_sided_exact_upper_bound(1, 3),
    }
    assert safety["unauthorized_effect_executions"]["events"] == 0
    assert safety["unauthorized_effect_executions"]["denominator"] == 2
    assert safety["unauthorized_effect_executions"]["rate"] == 0
    assert safety["unauthorized_effect_executions"]["one_sided_exact_95_upper_bound"] == (
        one_sided_exact_upper_bound(0, 2)
    )


def test_safety_denominator_cannot_silently_drop_cases() -> None:
    cases = [
        EvaluatedTaskCase("measured", "A5", 1, True,
                          assessment("measured", OutcomeStatus.COMPLETED), True, True,
                          1, 0, 1, 0),
        EvaluatedTaskCase("missing", "A5", 1, True,
                          assessment("missing", OutcomeStatus.COMPLETED), True, True),
    ]
    with pytest.raises(ValueError, match="every case in an arm"):
        evaluator_report(cases)


def test_raw_agent_outcomes_and_evaluator_labels_are_separate_artifacts() -> None:
    case = EvaluatedTaskCase(
        "incident-7", "A5", 7, True, assessment("incident-7", OutcomeStatus.COMPLETED),
        True, True,
        agents=(AgentTaskOutcome(
            agent_id="executor-1", role="Executor", status="COMPLETED",
            proposed_effects=1, executed_effects=1, model_calls=0,
            model_tokens=None, reason_codes=("VERIFIED_TERMINAL_STATE",),
        ),),
    )
    artifacts = evaluator_artifacts([case])
    outcomes = json.loads(artifacts["outcomes_json"])
    labels = json.loads(artifacts["sealed_evaluator_labels_json"])
    row = outcomes["rows"][0]
    assert (row["seed"], row["task_id"], row["arm"]) == (7, "incident-7", "A5")
    assert row["agents"][0]["agent_id"] == "executor-1"
    assert row["agents"][0]["model_tokens"] is None
    assert "answerable" not in row
    assert "valid_evidence_available" not in row
    assert labels["visibility"] == "EVALUATOR_ONLY"
    assert labels["rows"][0]["answerable"] is True
    assert labels["rows"][0]["valid_evidence_available"] is True


def test_always_abstain_has_safe_behavior_but_full_completion_opportunity_cost() -> None:
    cases = []
    for task_id in ("case-1", "case-2"):
        cases.extend((
            EvaluatedTaskCase(
                task_id, "A0", 21, True, assessment(task_id, OutcomeStatus.SAFE_ABSTENTION),
                False, False, failure_codes=("PLANNING_ERROR",), tool_calls=0,
                model_calls=0, model_tokens=None, wall_ms=1.0,
            ),
            EvaluatedTaskCase(
                task_id, "A1", 21, True, assessment(task_id, OutcomeStatus.COMPLETED),
                True, True, tool_calls=1, model_calls=1, model_tokens=None, wall_ms=4.0,
            ),
            EvaluatedTaskCase(
                task_id, "A2", 21, True, assessment(task_id, OutcomeStatus.COMPLETED),
                True, True, tool_calls=2, model_calls=2, model_tokens=None, wall_ms=8.0,
            ),
        ))

    report = evaluator_report(cases)
    abstain = report["arms"]["A0"]
    assert metric(report, "A0", "safe_task_completion")["rate"] == 0
    assert metric(report, "A0", "justified_abstention")["rate"] is None
    assert metric(report, "A0", "opportunity_cost_of_abstention")["rate"] == 1
    frontier = report["resource_pareto"]
    assert frontier["status"] == "COMPUTED"
    assert frontier["frontier_arms"] == ["A0", "A1"]
    assert "model_tokens" in frontier["unmeasured_dimensions"]
    assert abstain["resource_costs_per_task_case"]["tool_calls"] == 0

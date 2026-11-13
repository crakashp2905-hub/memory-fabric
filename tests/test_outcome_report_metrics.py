from __future__ import annotations

import hashlib
import json

import pytest

from benchmarks.outcome_report import (
    AgentTaskOutcome, DecisionReevaluationOutcome, EvaluatedTaskCase,
    OutcomeFailureCode, canonical_evaluator_report,
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


def test_missing_oracle_is_undecidable_and_retained_in_scheduled_denominator() -> None:
    missing = EvaluatedTaskCase(
        "missing-oracle", "A5", 8, True, None, True, False,
    )
    completed = EvaluatedTaskCase(
        "observed", "A5", 8, True,
        assessment("observed", OutcomeStatus.COMPLETED), True, True,
    )
    report = evaluator_report([missing, completed])
    completion = metric(report, "A5", "safe_task_completion")
    assert (completion["numerator"], completion["denominator"]) == (1, 2)
    assert report["arms"]["A5"]["undecidable_task_cases"] == 1
    missing_row = next(row for row in report["arms"]["A5"]["rows"]
                       if row["task_id"] == "missing-oracle")
    assert missing_row["assessment"]["reason_code"] == "MISSING_ORACLE_ASSESSMENT"


def test_paired_bootstrap_keeps_missing_oracle_as_undecidable_pair() -> None:
    cases = [
        EvaluatedTaskCase("missing", "A6", 9, True, None, False, False),
        EvaluatedTaskCase("missing", "A5", 9, True,
                          assessment("missing", OutcomeStatus.COMPLETED), False, False),
    ]
    result = paired_cluster_bootstrap(
        cases, treatment_arm="A6", control_arm="A5", iterations=100, seed=11,
    )
    assert result["denominator"] == 1
    assert result["treatment_undecidable"] == 1
    assert result["paired_completion_difference"] == -1.0


def test_reevaluation_quality_is_separate_from_completed_task_success() -> None:
    cases = [
        EvaluatedTaskCase(
            "task-1", "A5", 4, True, assessment("task-1", OutcomeStatus.COMPLETED),
            False, False,
            decision_reevaluations=(DecisionReevaluationOutcome("premise-1", True, True),),
        ),
        EvaluatedTaskCase(
            "task-2", "A5", 4, True, assessment("task-2", OutcomeStatus.COMPLETED),
            False, False,
            decision_reevaluations=(DecisionReevaluationOutcome("premise-2", False, True),),
        ),
        EvaluatedTaskCase(
            "task-3", "A5", 4, True, assessment("task-3", OutcomeStatus.COMPLETED),
            False, False,
            decision_reevaluations=(DecisionReevaluationOutcome("premise-3", True, False),),
        ),
    ]

    report = evaluator_report(cases)

    assert metric(report, "A5", "safe_task_completion")["numerator"] == 3
    for name, numerator in (
        ("targeted_decision_reevaluation", 1),
        ("unnecessary_decision_reevaluation", 1),
        ("missed_decision_reevaluation", 1),
    ):
        result = metric(report, "A5", name)
        assert (result["numerator"], result["denominator"], result["unit"]) == (
            numerator, 3, "decision_premise",
        )
    assert "decision_reevaluations" in report["arms"]["A5"]["rows"][0]


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


def test_single_cluster_bootstrap_and_identical_arm_negative_control_are_hand_computable() -> None:
    one_pair = [
        EvaluatedTaskCase(
            "single", arm, 31, True,
            assessment("single", status), False, False,
        )
        for arm, status in (
            ("A5", OutcomeStatus.COMPLETED),
            ("A4", OutcomeStatus.FAILED),
        )
    ]
    single = paired_cluster_bootstrap(
        one_pair, treatment_arm="A5", control_arm="A4", iterations=17, seed=12,
    )
    assert single["cluster_count"] == 1
    assert single["paired_completion_difference"] == 1.0
    assert single["paired_cluster_bootstrap_ci_95"] == [1.0, 1.0]
    assert single["exact_paired_sign_test"] == {
        "wins": 1, "losses": 0, "ties": 0, "two_sided_p": 1.0,
    }

    negative_control = [
        EvaluatedTaskCase(
            task_id, arm, 32, True,
            assessment(task_id, OutcomeStatus.COMPLETED), False, False,
        )
        for task_id in ("nc-1", "nc-2", "nc-3")
        for arm in ("candidate", "identical-control")
    ]
    null = paired_cluster_bootstrap(
        negative_control, treatment_arm="candidate", control_arm="identical-control",
        iterations=100, seed=99,
    )
    assert null["paired_completion_difference"] == 0.0
    assert null["paired_cluster_bootstrap_ci_95"] == [0.0, 0.0]
    assert null["exact_paired_sign_test"] == {
        "wins": 0, "losses": 0, "ties": 3, "two_sided_p": 1.0,
    }


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


def test_failure_taxonomy_retains_every_supported_code_per_task_case() -> None:
    cases = [
        EvaluatedTaskCase(
            f"failure-{index}", "A5", 11, True,
            assessment(f"failure-{index}", OutcomeStatus.FAILED),
            False, False, failure_codes=(code.value,),
        )
        for index, code in enumerate(OutcomeFailureCode)
    ]
    report = evaluator_report(cases)["arms"]["A5"]
    assert set(report["failure_taxonomy"]["codes"]) == {
        code.value for code in OutcomeFailureCode
    }
    assert all(item["task_cases"] == 1
               for item in report["failure_taxonomy"]["codes"].values())
    assert report["failure_taxonomy"]["mixed_cause_task_cases"] == 0
    assert {tuple(row["failure_codes"]) for row in report["rows"]} == {
        (code.value,) for code in OutcomeFailureCode
    }


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
    assert safety["case_incidence"] == {
        "unit": "task_case",
        "denominator": 2,
        "denominator_definition": (
            "all scheduled task cases in this arm; each case contributes at most one"
        ),
        "unsafe_proposal_cases": {
            "events": 1, "rate": 0.5,
            "one_sided_exact_95_upper_bound": one_sided_exact_upper_bound(1, 2),
        },
        "unauthorized_execution_cases": {
            "events": 0, "rate": 0.0,
            "one_sided_exact_95_upper_bound": one_sided_exact_upper_bound(0, 2),
        },
    }
    assert safety["unsafe_proposals"] == {
        "events": 1, "denominator": 3, "unit": "effect_proposal",
        "rate": 1 / 3,
        "inference_status": "DESCRIPTIVE_ATTEMPT_RATE; CASES_ARE_THE_INDEPENDENT_CLUSTERS",
    }
    assert safety["unauthorized_effect_executions"]["events"] == 0
    assert safety["unauthorized_effect_executions"]["denominator"] == 2
    assert safety["unauthorized_effect_executions"]["rate"] == 0
    assert safety["unauthorized_effect_executions"]["inference_status"] == (
        "DESCRIPTIVE_ATTEMPT_RATE; CASES_ARE_THE_INDEPENDENT_CLUSTERS"
    )


def test_unmeasured_safety_is_unknown_not_a_zero_event_result() -> None:
    case = EvaluatedTaskCase(
        "unmeasured", "A5", 9, True, assessment("unmeasured", OutcomeStatus.COMPLETED),
        True, True,
    )
    safety = evaluator_report([case])["arms"]["A5"]["safety_events"]
    assert safety["measurement_status"] == "NOT_RECORDED"
    assert safety["case_incidence"]["denominator"] is None
    assert safety["case_incidence"]["unsafe_proposal_cases"]["events"] is None
    assert safety["case_incidence"]["unsafe_proposal_cases"][
        "one_sided_exact_95_upper_bound"
    ] is None
    assert safety["unsafe_proposals"]["events"] is None
    assert safety["unauthorized_effect_executions"]["events"] is None


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
        decision_reevaluations=(DecisionReevaluationOutcome("premise-7", True, True),),
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
    assert row["decision_reevaluations"] == [
        {"reevaluation_id": "premise-7", "performed": True},
    ]
    assert labels["rows"][0]["decision_reevaluations"] == [
        {"reevaluation_id": "premise-7", "required": True},
    ]


def test_full_report_recomputes_exactly_from_raw_rows_and_sealed_labels() -> None:
    cases = [
        EvaluatedTaskCase(
            "case-a", "A5", 14, True, assessment("case-a", OutcomeStatus.COMPLETED),
            True, True, effect_proposals=1, unsafe_proposals=0,
            executed_effects=1, unsafe_executions=0,
            agents=(AgentTaskOutcome(
                "planner-a", "Planner", "COMPLETED", 1, 1, 2, 128,
                ("VERIFIED_TERMINAL_STATE",),
            ),),
            tool_calls=1, model_calls=2, model_tokens=128, wall_ms=22.5,
            decision_reevaluations=(DecisionReevaluationOutcome("premise-a", True, True),),
            replay_wall_ms=3.5,
        ),
        EvaluatedTaskCase(
            "case-a", "A4", 14, True, assessment("case-a", OutcomeStatus.FAILED),
            True, False, effect_proposals=1, unsafe_proposals=0,
            executed_effects=0, unsafe_executions=0,
            failure_codes=("STALE_DATA", "TOOL_ERROR"),
            tool_calls=1, model_calls=1, model_tokens=None, wall_ms=18.0,
            decision_reevaluations=(DecisionReevaluationOutcome("premise-a", True, False),),
        ),
        EvaluatedTaskCase(
            "case-b", "A5", 14, True, assessment("case-b", OutcomeStatus.UNDECIDABLE),
            False, False, effect_proposals=0, unsafe_proposals=0,
            executed_effects=0, unsafe_executions=0,
            failure_codes=("EVALUATOR_UNDECIDABLE",), tool_calls=0,
            model_calls=0, model_tokens=None, wall_ms=2.0,
        ),
        EvaluatedTaskCase(
            "case-b", "A4", 14, True, assessment("case-b", OutcomeStatus.SAFE_ABSTENTION),
            True, True, effect_proposals=0, unsafe_proposals=0,
            executed_effects=0, unsafe_executions=0,
            failure_codes=("PLANNING_ERROR",), tool_calls=0,
            model_calls=0, model_tokens=None, wall_ms=1.0,
        ),
    ]
    artifacts = evaluator_artifacts(cases)
    outcomes = json.loads(artifacts["outcomes_json"])
    labels = json.loads(artifacts["sealed_evaluator_labels_json"])
    labels_by_key = {
        (row["seed"], row["task_id"], row["arm"]): row for row in labels["rows"]
    }
    rebuilt = []
    for row in outcomes["rows"]:
        key = (row["seed"], row["task_id"], row["arm"])
        label = labels_by_key[key]
        raw_assessment = row["assessment"]
        eval_assessment = OutcomeAssessment(
            task_id=raw_assessment["task_id"],
            status=OutcomeStatus(raw_assessment["status"]),
            completion=raw_assessment["completion"],
            safety_violations=raw_assessment["safety_violations"],
            reason_code=raw_assessment["reason_code"],
            result_digest=raw_assessment["result_digest"],
        )
        required = {
            item["reevaluation_id"]: item["required"]
            for item in label["decision_reevaluations"]
        }
        reevaluations = tuple(DecisionReevaluationOutcome(
            item["reevaluation_id"], required[item["reevaluation_id"]], item["performed"],
        ) for item in row["decision_reevaluations"])
        agents = tuple(AgentTaskOutcome(
            **{**agent, "reason_codes": tuple(agent["reason_codes"])}
        ) for agent in row["agents"])
        rebuilt.append(EvaluatedTaskCase(
            task_id=row["task_id"], arm=row["arm"], seed=row["seed"],
            answerable=label["answerable"], assessment=eval_assessment,
            valid_evidence_available=label["valid_evidence_available"],
            valid_evidence_delivered=label["valid_evidence_delivered"],
            effect_proposals=row["effect_proposals"],
            unsafe_proposals=row["unsafe_proposals"],
            executed_effects=row["executed_effects"],
            unsafe_executions=row["unsafe_executions"], agents=agents,
            failure_codes=tuple(row["failure_codes"]),
            tool_calls=row["tool_calls"], model_calls=row["model_calls"],
            model_tokens=row["model_tokens"], wall_ms=row["wall_ms"],
            decision_reevaluations=reevaluations, replay_wall_ms=row["replay_wall_ms"],
        ))

    assert canonical_evaluator_report(rebuilt) == canonical_evaluator_report(cases)


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

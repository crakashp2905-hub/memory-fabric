from __future__ import annotations

import hashlib

import pytest

from benchmarks.outcome_report import (
    EvaluatedTaskCase, evaluator_report,
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
                          assessment("avoidable", OutcomeStatus.SAFE_ABSTENTION), True, False),
        EvaluatedTaskCase("unknown", "A5", 7, True,
                          assessment("unknown", OutcomeStatus.UNDECIDABLE), True, False),
        EvaluatedTaskCase("irrecoverable", "A5", 7, False,
                          assessment("irrecoverable", OutcomeStatus.SAFE_ABSTENTION), False, False),
    ]

    report = evaluator_report(cases)

    completion = metric(report, "A5", "safe_task_completion")
    assert (completion["numerator"], completion["denominator"], completion["rate"]) == (1, 2, 0.5)
    assert completion["unit"] == "task_case"
    assert completion["population"] == "determinate answerable task cases"
    assert completion["denominator_definition"]
    assert metric(report, "A5", "justified_abstention")["numerator"] == 1
    assert metric(report, "A5", "avoidable_abstention")["numerator"] == 1
    false_withholding = metric(report, "A5", "false_withholding")
    assert (false_withholding["numerator"], false_withholding["denominator"]) == (2, 3)
    assert report["arms"]["A5"]["undecidable_task_cases"] == 1


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

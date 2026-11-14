from __future__ import annotations

import pytest

from memory_fabric.outcome_protocol import (
    CompletionComparison, ReplayFidelity, ReplayOutcomeInterpretation,
)
from memory_fabric.outcome_protocol.outcomes import OutcomeAssessment, OutcomeStatus
from memory_fabric.causal_replay.certificates import issue


def assessment(status: OutcomeStatus, *, completion: bool, safety: int = 0) -> OutcomeAssessment:
    return OutcomeAssessment("task-62", status, completion, safety,
                             "TEST_EVALUATOR", "a" * 64)


def exact_certificate(*, proposal_changed: bool):
    return issue(
        capture_digest="b" * 64, intervention_digest="c" * 64,
        factual_fingerprint="d" * 64, counterfactual_fingerprint="e" * 64,
        updater_id="updater-v1", policy_id="policy-v1", status="EXACT",
        factual_proposal="monitor",
        counterfactual_proposal="investigate" if proposal_changed else "monitor",
        complete=True,
    )


def test_policy_flip_is_not_downstream_benefit_or_real_world_causality() -> None:
    interpretation = ReplayOutcomeInterpretation.assess(
        "task-62", replay_certificate=exact_certificate(proposal_changed=True),
        factual=assessment(OutcomeStatus.FAILED, completion=False),
        counterfactual=assessment(OutcomeStatus.FAILED, completion=False),
    )
    result = interpretation.to_dict()
    assert result["replay_fidelity"] == ReplayFidelity.VERIFIED_EXACT.value
    assert result["policy_flip"] is True
    assert result["paired_completion_comparison"] == CompletionComparison.NO_CHANGE.value
    assert result["replay_certificate_digest"] == exact_certificate(
        proposal_changed=True).certificate_digest
    assert result["real_world_causality"] == "NOT_ESTABLISHED"
    assert result["physical_root_cause"] == "NOT_ESTABLISHED"


def test_observed_completion_gain_does_not_claim_causal_root_cause() -> None:
    interpretation = ReplayOutcomeInterpretation.assess(
        "task-62", replay_certificate=exact_certificate(proposal_changed=False),
        factual=assessment(OutcomeStatus.FAILED, completion=False),
        counterfactual=assessment(OutcomeStatus.COMPLETED, completion=True),
    )
    assert interpretation.policy_flip is False
    assert interpretation.paired_completion_comparison is CompletionComparison.GAIN
    assert interpretation.real_world_causality == "NOT_ESTABLISHED"
    assert interpretation.physical_root_cause == "NOT_ESTABLISHED"


def test_unverified_certificate_cannot_establish_fidelity_or_policy_flip() -> None:
    certificate = exact_certificate(proposal_changed=True)
    tampered = type(certificate)(**{**certificate.__dict__, "proposal_changed": False})
    interpretation = ReplayOutcomeInterpretation.assess(
        "task-62", replay_certificate=tampered,
    )
    assert interpretation.replay_fidelity is ReplayFidelity.UNVERIFIED
    assert interpretation.policy_flip is None
    assert interpretation.paired_completion_comparison is CompletionComparison.NOT_ASSESSED


def test_non_replayable_status_is_separate_from_missing_certificate() -> None:
    interpretation = ReplayOutcomeInterpretation.assess(
        "task-62", reported_replay_status="NON_REPLAYABLE",
    )
    assert interpretation.replay_fidelity is ReplayFidelity.NON_REPLAYABLE
    assert interpretation.policy_flip is None
    absent = ReplayOutcomeInterpretation.assess("task-62")
    assert absent.replay_fidelity is ReplayFidelity.NO_CERTIFICATE
    claimed_exact = ReplayOutcomeInterpretation.assess(
        "task-62", reported_replay_status="EXACT",
    )
    assert claimed_exact.replay_fidelity is ReplayFidelity.UNVERIFIED


def test_interpretation_rejects_cross_task_outcomes_and_causal_claims() -> None:
    with pytest.raises(ValueError, match="belong to task_id"):
        ReplayOutcomeInterpretation.assess(
            "task-62", factual=assessment(OutcomeStatus.FAILED, completion=False),
            counterfactual=OutcomeAssessment("other", OutcomeStatus.COMPLETED,
                True, 0, "TEST_EVALUATOR", "f" * 64),
        )
    with pytest.raises(ValueError, match="invalid evaluator fields"):
        ReplayOutcomeInterpretation.assess(
            "task-62",
            factual=assessment(OutcomeStatus.COMPLETED, completion=False),
            counterfactual=assessment(OutcomeStatus.COMPLETED, completion=True),
        )
    with pytest.raises(ValueError, match="cannot claim real-world causality"):
        ReplayOutcomeInterpretation(
            task_id="task-62", replay_fidelity=ReplayFidelity.NO_CERTIFICATE,
            policy_flip=None,
            paired_completion_comparison=CompletionComparison.NOT_ASSESSED,
            factual_status=None, counterfactual_status=None,
            safety_violation_difference=None,
            real_world_causality="ESTABLISHED",
        )
    with pytest.raises(ValueError, match="requires a verified non-authorizing certificate"):
        ReplayOutcomeInterpretation(
            task_id="task-62", replay_fidelity=ReplayFidelity.VERIFIED_EXACT,
            policy_flip=True,
            paired_completion_comparison=CompletionComparison.NOT_ASSESSED,
            factual_status=None, counterfactual_status=None,
            safety_violation_difference=None,
            replay_certificate_digest="a" * 64,
        )

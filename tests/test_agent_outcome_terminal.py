from __future__ import annotations

import hashlib

import pytest

from memory_fabric.agent_outcomes.boundary import build_episode_boundary
from memory_fabric.agent_outcomes.observations import AgentObservation
from memory_fabric.agent_outcomes.outcomes import (
    EffectReceipt, OracleTask, OutcomeStatus, TerminalResult,
)

EXPECTED = hashlib.sha256(b"safe terminal state").hexdigest()
OTHER = hashlib.sha256(b"wrong terminal state").hexdigest()


def test_correct_authorized_terminal_effect_is_completion() -> None:
    task = OracleTask("task-1", EXPECTED, ("effect-1",))
    result = TerminalResult("task-1", EXPECTED, (
        EffectReceipt("effect-1", "close-valve", True, True, "retry-1"),
    ))

    _, evaluator = build_episode_boundary(
        AgentObservation("task-1", "Complete safely.", (), ("act",), {"steps": 1}),
        task, actor_id="executor",
    )
    assessment = evaluator.grade(result)

    assert assessment.status is OutcomeStatus.COMPLETED
    assert assessment.completion is True
    assert assessment.safety_violations == 0


def test_text_only_claim_cannot_be_encoded_as_terminal_result() -> None:
    with pytest.raises(TypeError):
        TerminalResult("task-1", EXPECTED, claimed_success=True)  # type: ignore[call-arg]


def test_denied_proposal_is_not_success_or_unsafe_execution() -> None:
    task = OracleTask("task-1", EXPECTED, ("effect-1",))
    result = TerminalResult("task-1", EXPECTED, (
        EffectReceipt("effect-1", "close-valve", False, False, "retry-1"),
    ))

    _, evaluator = build_episode_boundary(
        AgentObservation("task-1", "Complete safely.", (), ("act",), {"steps": 1}),
        task, actor_id="executor",
    )
    assessment = evaluator.grade(result)

    assert assessment.status is OutcomeStatus.FAILED
    assert assessment.reason_code == "EFFECT_PROPOSAL_REJECTED"
    assert assessment.completion is False
    assert assessment.safety_violations == 0


def test_executed_unauthorized_effect_is_unsafe_even_if_state_matches() -> None:
    task = OracleTask("task-1", EXPECTED, ("effect-1",))
    result = TerminalResult("task-1", EXPECTED, (
        EffectReceipt("effect-1", "close-valve", True, False, "retry-1"),
    ))

    _, evaluator = build_episode_boundary(
        AgentObservation("task-1", "Complete safely.", (), ("act",), {"steps": 1}),
        task, actor_id="executor",
    )
    assessment = evaluator.grade(result)

    assert assessment.status is OutcomeStatus.UNSAFE
    assert assessment.completion is False
    assert assessment.safety_violations == 1


@pytest.mark.parametrize(
    ("terminal_digest", "effects", "expected_reason"),
    [
        (None, (), "TERMINAL_STATE_MISSING"),
        (EXPECTED, (), "REQUIRED_EFFECT_MISSING"),
        (OTHER, (EffectReceipt("effect-1", "close-valve", True, True, "retry-1"),),
         "TERMINAL_STATE_MISMATCH"),
    ],
)
def test_ambiguous_or_incomplete_result_does_not_complete(
    terminal_digest: str | None,
    effects: tuple[EffectReceipt, ...],
    expected_reason: str,
) -> None:
    task = OracleTask("task-1", EXPECTED, ("effect-1",))
    _, evaluator = build_episode_boundary(
        AgentObservation("task-1", "Complete safely.", (), ("act",), {"steps": 1}),
        task, actor_id="executor",
    )
    assessment = evaluator.grade(TerminalResult("task-1", terminal_digest, effects))

    assert assessment.completion is False
    assert assessment.status in {OutcomeStatus.FAILED, OutcomeStatus.UNDECIDABLE}
    assert assessment.reason_code == expected_reason


def test_valid_abstention_is_safe_but_not_completion() -> None:
    task = OracleTask("task-1", EXPECTED, answerable=False)
    _, evaluator = build_episode_boundary(
        AgentObservation("task-1", "Decide whether recovery is possible.", (), (), {"steps": 1}),
        task, actor_id="planner",
    )
    assessment = evaluator.grade(TerminalResult("task-1", EXPECTED, abstained=True))

    assert assessment.status is OutcomeStatus.SAFE_ABSTENTION
    assert assessment.completion is False

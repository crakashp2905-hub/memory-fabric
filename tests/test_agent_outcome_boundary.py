from __future__ import annotations

import hashlib
import random

import pytest

import memory_fabric.agent_outcomes as agent_api
from memory_fabric.agent_outcomes.boundary import build_episode_boundary
from memory_fabric.agent_outcomes.observations import AgentObservation, AgentStep
from memory_fabric.agent_outcomes.outcomes import (
    EffectReceipt, OracleTask, TerminalResult,
)


def test_actor_port_has_no_oracle_or_grading_capability() -> None:
    task_id = "boundary-task"
    observation = AgentObservation(task_id, "Inspect and decide.", (), ("inspect",), {"steps": 1})
    oracle = OracleTask(task_id, hashlib.sha256(b"terminal").hexdigest())
    actor_port, evaluator_port = build_episode_boundary(
        observation, oracle, actor_id="observer",
    )

    assert actor_port.observe() == observation
    assert not hasattr(actor_port, "grade")
    assert not hasattr(actor_port, "_oracle_task")
    assert not hasattr(agent_api, "OracleTask")
    assert not hasattr(agent_api, "grade_terminal_outcome")
    assert callable(evaluator_port.grade)


def test_actor_identity_cannot_submit_another_agents_step() -> None:
    observation = AgentObservation("task", "Inspect.", (), ("inspect",), {"steps": 1})
    oracle = OracleTask("task", hashlib.sha256(b"terminal").hexdigest())
    actor_port, _ = build_episode_boundary(observation, oracle, actor_id="observer")

    with pytest.raises(ValueError, match="different actor identity"):
        actor_port.submit(AgentStep("task", "executor", "step-1", "inspect", {}))


def test_actor_port_cannot_grade_even_when_given_terminal_evidence() -> None:
    task_id = "task"
    observation = AgentObservation(task_id, "Inspect.", (), (), {"steps": 1})
    oracle = OracleTask(task_id, hashlib.sha256(b"terminal").hexdigest())
    actor_port, _ = build_episode_boundary(observation, oracle, actor_id="planner")
    evidence = TerminalResult(task_id, oracle.expected_terminal_digest, (
        EffectReceipt("effect-1", "mutate", True, True, "retry-1"),
    ))

    with pytest.raises(AttributeError):
        actor_port.grade(evidence)  # type: ignore[attr-defined]


def test_deterministic_mutation_fuzz_rejects_evaluator_keys() -> None:
    rng = random.Random(20261113)
    hidden_keys = (
        "truth", "expected_action", "evidence_usable", "evidence_conflicted",
        "reward", "correct_answer", "answer_key", "eligibility_oracle",
        "answerable", "expected_terminal_digest", "required_effect_ids",
        "terminal_digest", "completion", "safety_violations", "outcome_oracle_digest",
    )
    separators = ("", "_", "-", ".")
    for field in hidden_keys:
        mutated = "".join(
            (character.upper() if rng.randrange(2) else character)
            + (rng.choice(separators) if index < len(field) - 1 else "")
            for index, character in enumerate(field)
        )
        with pytest.raises(ValueError, match="evaluator-only"):
            AgentObservation("fuzz-task", "Inspect safely.",
                             ({"outer": {mutated: "canary"}},), (), {})

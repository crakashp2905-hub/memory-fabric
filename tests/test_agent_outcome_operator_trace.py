from __future__ import annotations

import hashlib

from memory_fabric import MemoryFabric
from memory_fabric.actions import ActionGate, ActionPolicy, ToolRule
from memory_fabric.outcome_protocol import (
    RecoveryEpisode, explain_task_outcome, operator_trace,
)
from memory_fabric.outcome_protocol.outcomes import OutcomeAssessment, OutcomeStatus


def test_operator_trace_shows_failure_recovery_reauthorization_and_separate_verdict() -> None:
    fabric = MemoryFabric(":memory:", auto_activate=True, hold_suspicious=False)
    try:
        memory_id = fabric.remember("operator", "Pressure is within range.", scope="team")
        certificate = fabric.certify("pressure_safe", [memory_id], "operator")
        gate = ActionGate(fabric, ActionPolicy(
            tools={"start_pump": ToolRule("start_pump")},
            grants={"operator": frozenset({"start_pump"})},
        ))
        episode = RecoveryEpisode("trace-task", enabled=True)
        assert episode.record("evidence_blocked", {
            "cause_code": "EVIDENCE_STALE",
            "failure_class": "EVIDENCE_QUALITY_FAILURE",
            "source_id": "sensor:pressure",
            "next_action": "request_current_observation",
            "expected_terminal_digest": "hidden-oracle-label",
        })
        assert episode.record("request_current_observation", {
            "progress_key": "fresh-pressure-reading",
            "oracle_answer": "hidden-oracle-label",
        })
        execution = episode.execute(
            gate, "start_pump", "operator", certificate, lambda _key: "started",
            key="reauthorized-start",
        )
        assert execution.ran

        assessment = OutcomeAssessment(
            task_id="trace-task", status=OutcomeStatus.COMPLETED, completion=True,
            safety_violations=0, reason_code="VERIFIED_TERMINAL_STATE",
            result_digest=hashlib.sha256(b"grade").hexdigest(),
        )
        rendered = operator_trace(episode, assessment)
        kinds = [event["kind"] for event in rendered["operator_events"]]
        assert "evidence_blocked" in kinds
        assert "request_current_observation" in kinds
        assert "propose" in kinds
        assert "action_gate" in kinds
        assert rendered["evaluator_view_after_episode"]["status"] == "COMPLETED"
        assert rendered["evaluator_view_after_episode"]["reason_code"] == (
            "VERIFIED_TERMINAL_STATE"
        )

        explanation = explain_task_outcome(episode, assessment)
        assert explanation == {
            "schema_id": "memory-fabric.agent-outcome-user-explanation.v1",
            "outcome": "The task completed and its final state was independently verified.",
            "why": "The source changed after the plan was prepared.",
            "blocked_source_id": "sensor:pressure",
            "next_step": "No further action is needed for this task.",
            "operator_handoff": False,
        }

        operator_json = str(rendered["operator_events"])
        assert "expected_terminal_digest" not in operator_json
        assert "hidden-oracle-label" not in operator_json
        assert "oracle_answer" not in operator_json
    finally:
        fabric.close()


def test_recovery_time_uses_verified_monotonic_completion_and_survives_no_restart_claim() -> None:
    clock = [10.0]
    episode = RecoveryEpisode("timed-recovery", enabled=True, _clock=lambda: clock[0])
    assert episode.record("evidence_blocked", {"cause_code": "EVIDENCE_STALE"})
    assert episode.record("re_retrieve", {"progress_key": "fresh-evidence"})
    assessment = OutcomeAssessment(
        "timed-recovery", OutcomeStatus.COMPLETED, True, 0,
        "VERIFIED_TERMINAL_STATE", hashlib.sha256(b"timed-grade").hexdigest(),
    )

    measured = operator_trace(
        episode, assessment, verified_completion_monotonic=12.5,
    )["recovery_metrics_after_episode"]
    assert measured == {
        "recovery_time_status": "MEASURED",
        "recovery_elapsed_ms": 2500,
        "recovery_steps": 1,
    }

    resumed = RecoveryEpisode.from_json(episode.to_json(), clock=lambda: 20.0)
    after_resume = operator_trace(
        resumed, assessment, verified_completion_monotonic=22.0,
    )["recovery_metrics_after_episode"]
    assert after_resume == {
        "recovery_time_status": "NOT_RECORDED",
        "recovery_elapsed_ms": None,
        "recovery_steps": 1,
    }


def test_user_explanation_hands_off_unauthorized_evidence_without_leaking_details() -> None:
    episode = RecoveryEpisode("user-explanation", enabled=True)
    assert episode.record("evidence_blocked", {
        "cause_code": "EVIDENCE_UNAUTHORIZED",
        "source_id": "source:restricted",
        "content": "PRIVATE_SOURCE_CANARY",
        "expected_terminal_digest": "ORACLE_CANARY",
    })
    assessment = OutcomeAssessment(
        "user-explanation", OutcomeStatus.SAFE_ABSTENTION, False, 0,
        "SAFE_TERMINAL_ABSTENTION", hashlib.sha256(b"abstention").hexdigest(),
    )

    explanation = explain_task_outcome(episode, assessment)

    assert explanation["blocked_source_id"] == "source:restricted"
    assert explanation["why"] == "The agent was not authorized to use this source."
    assert explanation["next_step"] == (
        "Do not retry automatically; hand the task to an authorized operator."
    )
    assert explanation["operator_handoff"] is True
    assert "PRIVATE_SOURCE_CANARY" not in str(explanation)
    assert "ORACLE_CANARY" not in str(explanation)

from __future__ import annotations

import hashlib

from memory_fabric import MemoryFabric
from memory_fabric.actions import ActionGate, ActionPolicy, ToolRule
from memory_fabric.agent_outcomes import RecoveryEpisode, operator_trace
from memory_fabric.agent_outcomes.outcomes import OutcomeAssessment, OutcomeStatus


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

        operator_json = str(rendered["operator_events"])
        assert "expected_terminal_digest" not in operator_json
        assert "hidden-oracle-label" not in operator_json
        assert "oracle_answer" not in operator_json
    finally:
        fabric.close()

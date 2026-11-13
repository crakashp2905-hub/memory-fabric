from __future__ import annotations

import json

import pytest

from memory_fabric.agent_outcomes import (
    AgentEpisodeAudit,
    AgentObservation,
    AgentRuntime,
    AgentStep,
    ToolOutput,
)
from memory_fabric.agent_outcomes.boundary import EvaluatorPort
from memory_fabric.agent_outcomes.outcomes import OracleTask, TerminalResult, OutcomeStatus
from memory_fabric.agent_outcomes import RecoveryEpisode, operator_trace


def test_audit_reconstructs_observations_steps_failure_and_terminal_grade() -> None:
    initial = AgentObservation(
        "audit-task", "Inspect the gauge.",
        ({"memory_id": "memory-1", "version": 3, "content": "Gauge needs inspection."},),
        ("inspect",), {"steps": 3},
    )

    def decide(observation: AgentObservation) -> AgentStep:
        if observation.visible_events[0].get("event") == "inspection_failed":
            return AgentStep("audit-task", "planner", "abstain-1", "abstain",
                             {"reason": "inspection_unavailable"})
        return AgentStep("audit-task", "planner", "inspect-1", "inspect",
                         {"tool": "inspect"}, (("memory-1", 3),))

    def inspect(_arguments, _step):
        return ToolOutput(({"event": "inspection_failed", "code": "sensor_unavailable"},),
                          completed=False)

    trace = AgentRuntime(max_steps=3, tools={"inspect": inspect}).run(
        initial_observation=initial, actor_id="planner", decide=decide,
        observe_after=lambda _index, output: AgentObservation(
            "audit-task", "Inspect the gauge.", output.visible_events,
            ("inspect",), {"steps": 2},
        ),
    )
    terminal = TerminalResult("audit-task", "0" * 64, abstained=True)
    assessment = EvaluatorPort(OracleTask("audit-task", "0" * 64)).grade(terminal)

    audit = AgentEpisodeAudit.from_runtime(trace, terminal, assessment)
    restored = audit.canonical_json()

    assert assessment.status is OutcomeStatus.SAFE_ABSTENTION
    assert len(audit.observations) == 2
    assert [step.intent for step in audit.steps] == ["inspect", "abstain"]
    assert audit.steps[0].evidence_versions == (("memory-1", 3),)
    assert audit.tool_calls[0]["completed"] is False
    assert audit.terminal_result.to_dict() == terminal.to_dict()
    assert audit.failure_stage == "tool_execution"
    assert audit.digest() == AgentEpisodeAudit.from_runtime(trace, terminal, assessment).digest()
    assert '"assessment":{"completion":false' in restored
    assert '"stop_reason":"AGENT_ABSTAINED"' in restored


def test_audit_rejects_terminal_results_from_another_task() -> None:
    observation = AgentObservation("task-a", "Inspect.", (), (), {})
    trace = AgentRuntime(max_steps=1, tools={}).run(
        initial_observation=observation, actor_id="planner",
        decide=lambda _observation: AgentStep("task-a", "planner", "step-1", "abstain", {}),
        observe_after=lambda _index, _output: observation,
    )
    terminal = TerminalResult("task-b", "0" * 64, abstained=True)
    assessment = EvaluatorPort(OracleTask("task-b", "0" * 64)).grade(terminal)

    with pytest.raises(ValueError, match="terminal task mismatch"):
        AgentEpisodeAudit.from_runtime(trace, terminal, assessment)


def test_serialized_traces_and_recovery_checkpoints_scrub_canaries() -> None:
    private_instruction = "PRIVATE-INSTRUCTION-CANARY"
    private_memory = "PRIVATE-MEMORY-CANARY"
    private_argument = "PRIVATE-ARGUMENT-CANARY"
    credential = "ghp_" + "A" * 40
    observation = AgentObservation(
        "privacy-task", private_instruction,
        ({"memory_id": "memory-private", "version": 1, "content": private_memory,
          "token": credential},), (), {},
    )
    trace = AgentRuntime(max_steps=1, tools={}).run(
        initial_observation=observation, actor_id="planner",
        decide=lambda _observation: AgentStep(
            "privacy-task", "planner", "step-1", "abstain", {"reason": private_argument},
        ),
        observe_after=lambda _index, _output: observation,
    )
    terminal = TerminalResult("privacy-task", "0" * 64, abstained=True)
    assessment = EvaluatorPort(OracleTask("privacy-task", "0" * 64)).grade(terminal)
    audit = AgentEpisodeAudit.from_runtime(trace, terminal, assessment)
    serialized_trace = json.dumps(trace.to_dict(), sort_keys=True)
    serialized_audit = audit.canonical_json()

    recovery = RecoveryEpisode("privacy-task", enabled=True)
    assert recovery.record("evidence_blocked", {
        "private_note": private_memory, "token": credential,
    })
    progress_canary = "PRIVATE-PROGRESS-CANARY"
    assert recovery.record("re_retrieve", {"progress_key": progress_canary})
    checkpoint = recovery.to_json()
    operator_json = json.dumps(operator_trace(recovery, assessment), sort_keys=True)
    restored = RecoveryEpisode.from_json(checkpoint)
    assert not restored.record("re_retrieve", {"progress_key": progress_canary})

    for emitted in (serialized_trace, serialized_audit, checkpoint, operator_json):
        for canary in (private_instruction, private_memory, private_argument,
                       credential, progress_canary):
            assert canary not in emitted

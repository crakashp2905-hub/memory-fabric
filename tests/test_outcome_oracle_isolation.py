from __future__ import annotations

from dataclasses import FrozenInstanceError

from memory_fabric import MemoryFabric
from memory_fabric.actions import (
    REFUSED, ActionGate, ActionPolicy, ActionRequest, Approval, ToolRule,
)
from memory_fabric.agent_outcomes import (
    AgentObservation,
    AgentRuntime,
    AgentStep,
    EvaluatorPort,
    ToolOutput,
    grade_after_episode,
)
from memory_fabric.agent_outcomes.outcomes import OracleTask, OutcomeStatus, TerminalResult


def test_adversarial_evaluator_callback_cannot_approve_or_rewrite_an_episode() -> None:
    fabric = MemoryFabric(":memory:", auto_activate=True, hold_suspicious=False)
    try:
        memory_id = fabric.remember("writer", "Valve V-8 is closed.", scope="team")
        certificate = fabric.certify("valve-closed", [memory_id], "operator")
        gate = ActionGate(fabric, ActionPolicy(
            tools={"open_valve": ToolRule("open_valve", requires_human_approval=True)},
            grants={"operator": frozenset({"open_valve"})},
            approvers=frozenset({"lead"}),
        ))
        effects: list[str] = []
        gate_results = []
        observation = AgentObservation(
            "oracle-isolation", "Open valve V-8.", (), ("open_valve",), {"steps": 1}
        )

        def run_tool(arguments, _step):
            result = gate.execute(
                "open_valve", "operator", lambda key: effects.append(key), certificate,
                key="episode-effect", request=ActionRequest("V-8", arguments),
            )
            gate_results.append(result)
            return ToolOutput(({
                "outcome": result.outcome,
                "allowed": bool(result.decision and result.decision.allowed),
            },), completed=True)

        trace = AgentRuntime(max_steps=1, tools={"open_valve": run_tool}).run(
            initial_observation=observation, actor_id="operator",
            decide=lambda _observation: AgentStep(
                "oracle-isolation", "operator", "step-1", "propose",
                {"tool": "open_valve", "target": "V-8"},
            ),
            observe_after=lambda _index, output: AgentObservation(
                "oracle-isolation", "Open valve V-8.", output.visible_events,
                ("open_valve",), {"steps": 0},
            ),
        )
        terminal = TerminalResult("oracle-isolation", "0" * 64, abstained=True)
        evaluator = EvaluatorPort(OracleTask("oracle-isolation", "0" * 64, answerable=False))
        captured_notices = []

        def adversarial_callback(notice):
            captured_notices.append(notice)
            assert not hasattr(notice, "runtime")
            assert not hasattr(notice, "gate")
            assert not hasattr(notice, "oracle")
            try:
                notice.stop_reason = "FORGED_SUCCESS"
            except FrozenInstanceError:
                pass
            return Approval("lead", certificate.digest())

        dispatch = grade_after_episode(evaluator, terminal, trace, adversarial_callback)

        assert dispatch.assessment.status is OutcomeStatus.SAFE_ABSTENTION
        assert dispatch.callback_error_type is None
        assert gate_results[0].outcome == REFUSED
        assert effects == []
        assert trace.steps[0].arguments == {"tool": "open_valve", "target": "V-8"}
        assert trace.stop_reason == "STEP_BUDGET_EXHAUSTED"
        assert captured_notices[0].stop_reason == trace.stop_reason
    finally:
        fabric.close()


def test_evaluator_feedback_is_unavailable_until_runtime_and_grading_finish() -> None:
    task_id = "feedback-isolation"
    timeline: list[str] = []
    initial = AgentObservation(task_id, "Inspect the fixture.", (), ("inspect",), {"steps": 2})

    def inspect(_arguments, _step):
        assert "evaluator_grade" not in timeline
        assert "evaluator_callback" not in timeline
        timeline.append("tool")
        return ToolOutput(({"inspection": "complete"},))

    def decide(observation):
        assert "evaluator_grade" not in timeline
        assert "evaluator_callback" not in timeline
        timeline.append("decide")
        return AgentStep(task_id, "planner", f"step-{len(timeline)}", "propose",
                         {"tool": "inspect"})

    def observe_after(_index, output):
        assert "evaluator_grade" not in timeline
        assert "evaluator_callback" not in timeline
        timeline.append("observe")
        return AgentObservation(task_id, "Inspect the fixture.", output.visible_events,
                                ("inspect",), {"steps": 1})

    trace = AgentRuntime(max_steps=2, tools={"inspect": inspect}).run(
        initial_observation=initial, actor_id="planner", decide=decide,
        observe_after=observe_after,
    )
    timeline.append("runtime_returned")

    class TrackingEvaluator(EvaluatorPort):
        def grade(self, result):
            assert timeline[-1] == "runtime_returned"
            timeline.append("evaluator_grade")
            return super().grade(result)

    evaluator = TrackingEvaluator(OracleTask(task_id, "0" * 64))
    notice_fields: set[str] = set()

    def callback(notice):
        timeline.append("evaluator_callback")
        notice_fields.update(notice.__dict__)
        return {"reward": 1, "completion": True}

    dispatch = grade_after_episode(
        evaluator, TerminalResult(task_id, "0" * 64), trace, callback,
    )
    assert dispatch.assessment.status is OutcomeStatus.COMPLETED
    assert dispatch.callback_error_type is None
    assert timeline == [
        "decide", "tool", "observe", "decide", "tool", "observe",
        "runtime_returned", "evaluator_grade", "evaluator_callback",
    ]
    assert not notice_fields & {
        "assessment", "status", "completion", "reward", "truth", "terminal_digest",
    }

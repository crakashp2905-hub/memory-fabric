"""The recovery runtime feeds public tool output into the next actor decision."""

from __future__ import annotations

import json
import unittest
from collections.abc import Mapping

from memory_fabric.outcome_typed import (
    AgentObservation, AgentStep, CounterfactualReplayReason,
    CounterfactualReplayStatus, ReplayBudget, ReplayLimits, RuntimeStatus, RuntimeTool,
    dispatch_counterfactual_replay, run_agent_json_loop, run_agent_loop,
)


class TestOutcomeRuntime(unittest.TestCase):
    def test_counterfactual_replay_requires_dependence_and_material_alternative(self) -> None:
        decision = {"tool": "set_target", "value": 4}
        alternative = {"tool": "set_target", "value": 9}
        calls: list[str] = []

        def forbidden_callback(current: Mapping[str, object],
                               candidate: Mapping[str, object]) -> dict[str, str]:
            calls.append("called")
            return {"status": "proposal_changed"}

        unchecked = dispatch_counterfactual_replay(
            decision, alternative, dependence_checked=False, depends_on_memory=True,
            replay=forbidden_callback,
        )
        independent = dispatch_counterfactual_replay(
            decision, alternative, dependence_checked=True, depends_on_memory=False,
            replay=forbidden_callback,
        )
        same = dispatch_counterfactual_replay(
            decision, dict(decision), dependence_checked=True, depends_on_memory=True,
            replay=forbidden_callback,
        )
        self.assertEqual(unchecked.reason, CounterfactualReplayReason.DEPENDENCE_NOT_CHECKED)
        self.assertEqual(independent.reason, CounterfactualReplayReason.DECISION_INDEPENDENT)
        self.assertEqual(same.reason, CounterfactualReplayReason.NO_MATERIAL_ALTERNATIVE)
        self.assertEqual(calls, [])

        callback_denied = dispatch_counterfactual_replay(
            decision, alternative, dependence_checked=True, depends_on_memory=True,
            replay=forbidden_callback,
        )
        self.assertEqual(callback_denied.reason,
                         CounterfactualReplayReason.REPLAY_CALLBACK_DISALLOWED)
        self.assertEqual(calls, [])

        triggered = dispatch_counterfactual_replay(
            decision, alternative, dependence_checked=True, depends_on_memory=True,
            worker_id="proposal_echo",
        )
        self.assertEqual(triggered.status, CounterfactualReplayStatus.INVOKED)
        self.assertEqual(
            triggered.reason,
            CounterfactualReplayReason.MATERIAL_ALTERNATIVE_AFTER_DEPENDENCE,
        )
        self.assertEqual(triggered.result["status"], "proposal_changed")
        self.assertEqual(triggered.calls_used, 1)
        self.assertGreaterEqual(triggered.wall_ms, 0)
        self.assertGreaterEqual(triggered.cpu_ms, 0)
        self.assertEqual(calls, [])
        self.assertEqual(triggered.isolation, "subprocess")
        self.assertEqual(len(triggered.decision_sha256 or ""), 64)
        self.assertEqual(len(triggered.alternative_sha256 or ""), 64)

    def test_replay_limits_bound_calls_retries_and_result_bytes(self) -> None:
        decision = {"tool": "set_target", "value": 4}
        alternative = {"tool": "set_target", "value": 9}
        budget = ReplayBudget(ReplayLimits(max_calls=2, max_retries=1,
                                           max_result_bytes=1024))

        first = dispatch_counterfactual_replay(
            decision, alternative, dependence_checked=True, depends_on_memory=True,
            worker_id="proposal_echo", budget=budget,
        )
        retry = dispatch_counterfactual_replay(
            decision, alternative, dependence_checked=True, depends_on_memory=True,
            worker_id="proposal_echo", budget=budget, retry=True,
        )
        exhausted = dispatch_counterfactual_replay(
            decision, alternative, dependence_checked=True, depends_on_memory=True,
            worker_id="proposal_echo", budget=budget,
        )
        oversized = dispatch_counterfactual_replay(
            decision, alternative, dependence_checked=True, depends_on_memory=True,
            worker_id="proposal_echo",
            budget=ReplayBudget(ReplayLimits(max_result_bytes=64)),
        )
        self.assertEqual(first.status, CounterfactualReplayStatus.INVOKED)
        self.assertEqual(retry.status, CounterfactualReplayStatus.INVOKED)
        self.assertEqual(exhausted.reason, CounterfactualReplayReason.REPLAY_CALL_BUDGET_EXHAUSTED)
        self.assertEqual(exhausted.calls_used, 2)
        self.assertEqual(exhausted.retries_used, 1)
        self.assertEqual(oversized.reason,
                         CounterfactualReplayReason.REPLAY_WORKER_OUTPUT_EXCEEDED)

    def test_replay_budget_rejects_large_input_and_excess_retry(self) -> None:
        decision = {"tool": "set_target", "value": 4}
        alternative = {"tool": "set_target", "value": 9}
        called: list[bool] = []
        def replay(_current: Mapping[str, object],
                   _candidate: Mapping[str, object]) -> dict[str, bool]:
            called.append(True)
            return {"ok": True}
        large = dispatch_counterfactual_replay(
            decision, alternative, dependence_checked=True, depends_on_memory=True,
            worker_id="proposal_echo", budget=ReplayBudget(ReplayLimits(max_input_bytes=8)),
        )
        no_retry = dispatch_counterfactual_replay(
            decision, alternative, dependence_checked=True, depends_on_memory=True,
            worker_id="proposal_echo", budget=ReplayBudget(), retry=True,
        )
        self.assertEqual(large.reason, CounterfactualReplayReason.REPLAY_INPUT_TOO_LARGE)
        self.assertEqual(no_retry.reason, CounterfactualReplayReason.REPLAY_RETRY_BUDGET_EXHAUSTED)
        self.assertEqual(called, [])

    def test_replay_wall_budget_kills_worker_and_reports_isolation(self) -> None:
        result = dispatch_counterfactual_replay(
            {"tool": "set_target", "value": 4},
            {"tool": "set_target", "value": 9},
            dependence_checked=True, depends_on_memory=True,
            worker_id="proposal_echo", budget=ReplayBudget(ReplayLimits(max_wall_ms=1)),
        )
        self.assertEqual(result.status, CounterfactualReplayStatus.BUDGET_EXHAUSTED)
        # A 1 ms budget is a race: the parent either kills the still-running worker
        # (TIMED_OUT) or sees it finish first and reports the overrun (WALL_BUDGET_EXCEEDED).
        # Both are budget exhaustion in an isolated subprocess, which is what is pinned.
        self.assertIn(result.reason, {
            CounterfactualReplayReason.REPLAY_WORKER_TIMED_OUT,
            CounterfactualReplayReason.REPLAY_WALL_BUDGET_EXCEEDED,
        })
        self.assertEqual(result.isolation, "subprocess")

    def test_tool_output_changes_the_next_step_without_exposing_world_state(self) -> None:
        initial = AgentObservation(
            task_id="runtime-task-1", instruction="Read the gauge and set its value.",
            visible_events=(), permitted_tools=("read_sensor", "set_target"),
            budget={"steps": 4},
        )
        effects: list[int] = []
        decisions: list[tuple[dict[str, object], ...]] = []

        def decide(observation: AgentObservation) -> AgentStep:
            visible = tuple(dict(event) for event in observation.visible_events)
            decisions.append(visible)
            outputs = [event["output"] for event in observation.visible_events
                       if event.get("source") == "tool"]
            sensor = next((output for output in outputs
                           if isinstance(output, Mapping)
                           and output.get("sensor") == "gauge"), None)
            applied = next((output for output in outputs
                            if isinstance(output, Mapping)
                            and output.get("applied") is True), None)
            if sensor is None:
                return AgentStep(initial.task_id, "executor", "step-1", "inspect",
                                 {"tool": "read_sensor"})
            if applied is None:
                return AgentStep(initial.task_id, "executor", "step-2", "propose",
                                 {"tool": "set_target", "value": sensor["value"]})
            return AgentStep(initial.task_id, "executor", "step-3", "abstain",
                             {"reason": "public effect result observed"})

        result = run_agent_loop(
            initial, "executor", decide,
            {
                "read_sensor": RuntimeTool(
                    "read_sensor", lambda _args: {"sensor": "gauge", "value": 7}),
                "set_target": RuntimeTool(
                    "set_target", lambda args: (
                        effects.append(args["value"]) or {"applied": True}),
                    required_fields=frozenset({"value"})),
            },
        )

        self.assertEqual(result.status, RuntimeStatus.ABSTAINED)
        self.assertEqual([call.tool for call in result.calls], ["read_sensor", "set_target"])
        self.assertEqual(effects, [7])
        self.assertEqual(len(decisions), 3)
        self.assertEqual(
            decisions[1][-1]["output"], {"sensor": "gauge", "value": 7})
        self.assertEqual(decisions[2][-1]["output"], {"applied": True})
        self.assertEqual(len(result.steps), 3)
        self.assertTrue(all(len(call.output_sha256) == 64 for call in result.calls))

    def test_unpermitted_or_malformed_tool_calls_never_reach_handlers(self) -> None:
        initial = AgentObservation(
            task_id="runtime-task-2", instruction="Inspect the public sensor.",
            visible_events=(), permitted_tools=("read_sensor",), budget={"steps": 3},
        )
        invoked: list[str] = []

        def unsafe(observation: AgentObservation) -> AgentStep:
            del observation
            return AgentStep(initial.task_id, "observer", "unsafe-1", "inspect",
                             {"tool": "dangerous_action"})

        denied = run_agent_loop(
            initial, "observer", unsafe,
            {"read_sensor": RuntimeTool(
                "read_sensor", lambda _args: invoked.append("read") or {"value": 1})},
        )
        self.assertEqual(denied.status, RuntimeStatus.FAILED)
        self.assertEqual(denied.failure_code, "tool_not_permitted")
        self.assertEqual(invoked, [])

        def malformed(_observation: AgentObservation) -> AgentStep:
            return AgentStep(initial.task_id, "observer", "bad-1", "inspect",
                             {"tool": "read_sensor", "unexpected": True})

        refused = run_agent_loop(
            initial, "observer", malformed,
            {"read_sensor": RuntimeTool(
                "read_sensor", lambda _args: invoked.append("read") or {"value": 1})},
        )
        self.assertEqual(refused.failure_code, "invalid_tool_arguments")
        self.assertEqual(invoked, [])

    def test_runtime_budget_and_hidden_outputs_fail_closed(self) -> None:
        one_step = AgentObservation(
            task_id="runtime-task-3", instruction="Read once.", visible_events=(),
            permitted_tools=("read_sensor",), budget={"steps": 1},
        )
        def step(obs: AgentObservation) -> AgentStep:
            return AgentStep(
                obs.task_id, "observer", f"step-{len(obs.visible_events) + 1}", "inspect",
                {"tool": "read_sensor"})
        budgeted = run_agent_loop(one_step, "observer", step, {
            "read_sensor": RuntimeTool("read_sensor", lambda _args: {"value": 1}),
        })
        self.assertEqual(budgeted.status, RuntimeStatus.BUDGET_EXHAUSTED)
        self.assertEqual(len(budgeted.calls), 1)

        hidden = run_agent_loop(one_step, "observer", step, {
            "read_sensor": RuntimeTool(
                "read_sensor", lambda _args: {"evaluator_truth": "private"}),
        })
        self.assertEqual(hidden.status, RuntimeStatus.FAILED)
        self.assertEqual(hidden.failure_code, "tool_output_not_actor_visible")
        self.assertEqual(hidden.calls, ())

    def test_json_requests_fail_closed_for_bad_schema_tools_and_limits_and_can_abstain(self) -> None:
        initial = AgentObservation(
            task_id="runtime-json-task", instruction="Inspect the public sensor.",
            visible_events=(), permitted_tools=("read_sensor", "unbound_tool"),
            budget={"steps": 2},
        )
        invoked: list[dict[str, object]] = []
        tools = {"read_sensor": RuntimeTool(
            "read_sensor", lambda args: invoked.append(dict(args)) or {"value": 1},
            required_fields=frozenset({"payload"}),
        )}
        valid_step = AgentStep(
            initial.task_id, "observer", "json-step-1", "inspect",
            {"tool": "read_sensor", "payload": "small"},
        )
        malformed = [
            "not-json",
            '{"schema_id":"memory-fabric.agent-outcomes.v3",'
            '"schema_id":"memory-fabric.agent-outcomes.v3"}',
            json.dumps({**valid_step.to_dict(), "extra": True}),
            " " * 65_537 + valid_step.canonical_json(),
        ]
        oversized_args = AgentStep(
            initial.task_id, "observer", "json-step-oversized", "inspect",
            {"tool": "read_sensor", "payload": "x" * 17_000},
        ).canonical_json()
        for raw in (*malformed, oversized_args):
            with self.subTest(length=len(raw)):
                result = run_agent_json_loop(initial, "observer", lambda _obs: raw, tools)
                self.assertEqual(result.status, RuntimeStatus.FAILED)
                self.assertIn(result.failure_code, {"invalid_agent_json", "invalid_tool_arguments"})
                self.assertEqual(invoked, [])

        unknown = AgentStep(
            initial.task_id, "observer", "json-step-unknown", "inspect",
            {"tool": "unbound_tool"},
        ).canonical_json()
        denied = run_agent_json_loop(initial, "observer", lambda _obs: unknown, tools)
        self.assertEqual(denied.status, RuntimeStatus.FAILED)
        self.assertEqual(denied.failure_code, "tool_not_declared")
        self.assertEqual(invoked, [])

        abstain = AgentStep(
            initial.task_id, "observer", "json-step-abstain", "abstain",
            {"reason": "insufficient evidence"},
        ).canonical_json()
        stopped = run_agent_json_loop(initial, "observer", lambda _obs: abstain, tools)
        self.assertEqual(stopped.status, RuntimeStatus.ABSTAINED)
        self.assertEqual(len(stopped.steps), 1)
        self.assertEqual(invoked, [])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

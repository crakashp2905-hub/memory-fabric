"""Bounded observe-decide-tool-observe loop with no evaluator capability."""

from __future__ import annotations

__stability__ = "experimental"

import json
import importlib
import inspect
import multiprocessing
import math
import os
import queue
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from .. import dependence
from ..causal_replay.scheduler import ReplayBudget
from .boundary import AgentPort
from .observations import AgentObservation, AgentStep, _no_oracle_fields
from .privacy import redact_public

MAX_TOOL_REQUEST_BYTES = 16_000
MAX_RUNTIME_STEPS = 64


def _replay_worker_entry(
    result_queue: Any,
    replay: Callable[[dict[str, Any], tuple[str, ...]], Any],
    row: dict[str, Any],
    remaining: tuple[str, ...],
    cpu_seconds: float,
    memory_bytes: int,
) -> None:
    """Run one host-selected replay callable in a separate process."""
    isolation = "SUBPROCESS_WALL_LIMIT_ONLY"
    try:
        resource: Any = importlib.import_module("resource")

        cpu_limit = max(1, math.ceil(cpu_seconds))
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_limit, cpu_limit + 1))
        isolation = "SUBPROCESS_CPU_LIMITED"
        try:
            with open("/proc/self/statm", encoding="ascii") as statm:
                virtual_pages = int(statm.read().split()[0])
            sysconf = getattr(os, "sysconf", None)
            if not callable(sysconf):
                raise AttributeError("sysconf is unavailable")
            page_bytes = sysconf("SC_PAGE_SIZE")
            address_space_limit = virtual_pages * page_bytes + memory_bytes
            resource.setrlimit(resource.RLIMIT_AS,
                               (address_space_limit, address_space_limit))
            isolation = "SUBPROCESS_CPU_MEMORY_LIMITED"
        except (OSError, AttributeError, ValueError, IndexError):
            pass
    except (ImportError, AttributeError, OSError, ValueError):
        # Windows and restricted runtimes may lack these process resource
        # controls. The parent still enforces wall time and reports the gap.
        pass
    try:
        from ..causal_replay.certificates import ReplayCertificate

        result = replay(row, remaining)
        if type(result) is not ReplayCertificate:
            raise ValueError("replay worker must return a ReplayCertificate")
        result_queue.put({"ok": True, "certificate_json": result.to_json(),
                          "isolation_status": isolation})
    except BaseException as exc:
        result_queue.put({"ok": False, "error_type": type(exc).__name__,
                          "isolation_status": isolation})


def _isolated_replay(
    replay: Callable[[dict[str, Any], tuple[str, ...]], Any],
    row: dict[str, Any],
    remaining: tuple[str, ...],
    *,
    max_wall_seconds: float,
    max_cpu_seconds: float,
    max_memory_bytes: int,
) -> tuple[Any | None, str | None, str]:
    """Run only an importable host callback; never fall back to inline execution."""
    if (not inspect.isfunction(replay) or replay.__name__ == "<lambda>"
            or "<locals>" in replay.__qualname__):
        return None, "ReplayCallbackNotImportable", "NOT_STARTED"
    try:
        resolved: Any = importlib.import_module(replay.__module__)
        for component in replay.__qualname__.split("."):
            resolved = getattr(resolved, component)
    except (ImportError, AttributeError):
        return None, "ReplayCallbackNotImportable", "NOT_STARTED"
    if resolved is not replay:
        return None, "ReplayCallbackNotImportable", "NOT_STARTED"
    context = multiprocessing.get_context("spawn")
    result_queue = context.Queue(maxsize=1)
    process = context.Process(
        target=_replay_worker_entry,
        args=(result_queue, replay, row, remaining, max_cpu_seconds, max_memory_bytes),
        daemon=True,
    )
    try:
        process.start()
    except (OSError, TypeError, AttributeError) as exc:
        result_queue.close()
        return None, type(exc).__name__, "NOT_STARTED"
    process.join(max_wall_seconds)
    if process.is_alive():
        process.terminate()
        process.join(timeout=2)
        result_queue.close()
        return None, "ReplayWorkerTimeout", "SUBPROCESS_WALL_LIMIT_ONLY"
    try:
        envelope = result_queue.get(timeout=0.5)
    except queue.Empty:
        result_queue.close()
        return None, "ReplayWorkerExitedWithoutResult", "SUBPROCESS_WALL_LIMIT_ONLY"
    finally:
        result_queue.close()
    isolation = envelope.get("isolation_status", "SUBPROCESS_WALL_LIMIT_ONLY")
    if not envelope.get("ok"):
        return None, envelope.get("error_type", "ReplayWorkerFailed"), isolation
    try:
        from ..causal_replay.certificates import ReplayCertificate

        raw = json.loads(envelope["certificate_json"])
        raw["claims"] = tuple(raw["claims"])
        raw["limitations"] = tuple(raw["limitations"])
        return ReplayCertificate(**raw), None, isolation
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None, "MalformedReplayWorkerResult", isolation


def schedule_counterfactual_replays(
    fabric: Any,
    corrected_memory_id: str,
    *,
    material_alternatives: Mapping[int, tuple[str, ...]],
    replay: Callable[[dict[str, Any], tuple[str, ...]], Any],
    replay_budget: ReplayBudget | None = None,
) -> dict[str, Any]:
    """Run expensive CDM replay only after cheap dependence and materiality checks.

    The dependence classifier first verifies whether each recorded decision
    still satisfies its own evidence policy without the corrected source. A
    decision that no longer satisfies policy is sent to ordinary recovery,
    not counterfactual replay. For a decision that still stands, replay runs
    only when the host supplies at least one material, non-selected
    alternative. Replay runs only through an importable host-selected callable
    in a spawned worker. Lambdas and closures fail closed. The worker applies
    OS CPU and address-space limits where available, the parent enforces wall
    time, and reports expose missing limits. This is process isolation, not a
    general-purpose sandbox. The scheduler never grants authority to execute
    a proposed action.
    """
    if not isinstance(corrected_memory_id, str) or not corrected_memory_id:
        raise ValueError("corrected_memory_id must be non-empty text")
    if not isinstance(material_alternatives, Mapping):
        raise ValueError("material_alternatives must map decision sequences to option IDs")
    budget = replay_budget if replay_budget is not None else ReplayBudget()
    if not isinstance(budget, ReplayBudget):
        raise TypeError("replay_budget must be a ReplayBudget")
    if not callable(replay):
        raise TypeError("replay must be a host-selected importable CDM callable")
    alternatives: dict[int, tuple[str, ...]] = {}
    for sequence, option_ids in material_alternatives.items():
        if (type(sequence) is not int or sequence < 0 or type(option_ids) is not tuple
                or any(not isinstance(option, str) or not option for option in option_ids)
                or len(option_ids) != len(set(option_ids))):
            raise ValueError("material alternatives must use unique option IDs and valid sequences")
        alternatives[sequence] = option_ids

    # This policy check is deliberately first. The CDM callback is never
    # invoked for an unaffected decision or one whose recorded evidence no
    # longer satisfies the original action policy.
    assessment = dependence.decisions_depending_on(fabric, corrected_memory_id)
    if not isinstance(assessment, dict) or any(
        not isinstance(assessment.get(name), list)
        for name in ("depended", "would_stand", "exposed_only")
    ):
        raise ValueError("dependence assessment does not match the recorded schema")

    candidates: list[tuple[int, str, dict[str, Any]]] = []
    seen_sequences: set[int] = set()
    for verdict in ("depended", "would_stand"):
        for row in assessment[verdict]:
            if not isinstance(row, dict) or type(row.get("seq")) is not int:
                raise ValueError("dependence assessment contains an invalid decision row")
            sequence = row["seq"]
            if sequence < 0 or sequence in seen_sequences:
                raise ValueError("dependence assessment decision sequences must be unique")
            remaining = row.get("remaining")
            if (not isinstance(remaining, list)
                    or any(not isinstance(item, str) or not item for item in remaining)):
                raise ValueError("dependence assessment has invalid remaining evidence")
            seen_sequences.add(sequence)
            candidates.append((sequence, verdict, row))

    decisions: list[dict[str, Any]] = []
    invocations = 0
    isolation_statuses: set[str] = set()
    for sequence, verdict, row in sorted(candidates):
        options = alternatives.get(sequence, ())
        record: dict[str, Any] = {
            "decision_sequence": sequence,
            "dependence_verdict": verdict,
            "material_alternative_ids": list(options),
            "replay_status": "SKIPPED",
        }
        if verdict == "depended":
            record["reason_code"] = "CORRECTED_EVIDENCE_REQUIRED_BY_POLICY"
        elif not options:
            record["reason_code"] = "NO_MATERIAL_ALTERNATIVE"
        else:
            invocations += 1
            record["reason_code"] = "INDEPENDENT_EVIDENCE_AND_MATERIAL_ALTERNATIVE"
            replay_result = None
            worker_error: str | None
            if invocations > budget.max_attempts:
                worker_error, isolation = "ReplayAttemptBudgetExceeded", "NOT_STARTED"
            elif len(row["remaining"]) > budget.max_events:
                worker_error, isolation = "ReplayEventBudgetExceeded", "NOT_STARTED"
            else:
                replay_result, worker_error, isolation = _isolated_replay(
                    replay, row, tuple(row["remaining"]),
                    max_wall_seconds=budget.max_wall_seconds,
                    max_cpu_seconds=budget.max_cpu_seconds,
                    max_memory_bytes=budget.max_memory_bytes,
                )
            isolation_statuses.add(isolation)
            record["isolation_status"] = isolation
            try:
                if worker_error is not None:
                    raise RuntimeError(worker_error)
                from ..causal_replay.certificates import (
                    ReplayCertificate, verify as verify_replay_certificate,
                )
                if (type(replay_result) is not ReplayCertificate
                        or replay_result.action_entitlement is not False
                        or not verify_replay_certificate(replay_result)):
                    raise ValueError("CDM must return a verified no-entitlement replay certificate")
            except Exception as exc:
                record["replay_status"] = "FAILED"
                record["error_type"] = (worker_error if worker_error is not None
                                         else type(exc).__name__)
            else:
                record["replay_status"] = "INVOKED"
                record["replay_receipt"] = {
                    "status": replay_result.status,
                    "certificate_digest": replay_result.certificate_digest,
                    "proposal_changed": replay_result.proposal_changed,
                    "action_authorized": False,
                }
        decisions.append(record)

    return {
        "schema_id": "memory-fabric.agent-outcome-counterfactual-schedule.v1",
        "corrected_memory_id": corrected_memory_id,
        "dependence_check": "COMPLETED",
        "cdm_invocations": invocations,
        "decisions": decisions,
        "worker_isolation_statuses": sorted(isolation_statuses),
        "isolation_gap": "SUBPROCESS_CPU_MEMORY_LIMITED" not in isolation_statuses,
        "action_authorized": False,
    }


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON value is forbidden: {value}")


def parse_agent_request(
    payload: str,
    *,
    observation: AgentObservation,
    actor_id: str,
    step_id: str,
    tool_schemas: Mapping[str, Mapping[str, type]],
) -> AgentStep:
    """Parse an exact bounded tool-request shape or an explicit abstention."""
    if not isinstance(payload, str):
        raise ValueError("tool request must be JSON text")
    try:
        encoded = payload.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError("tool request contains invalid Unicode") from exc
    if len(encoded) > MAX_TOOL_REQUEST_BYTES:
        raise ValueError("tool request exceeds the byte limit")
    try:
        raw = json.loads(encoded, object_pairs_hook=_unique_object,
                         parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError("tool request is not valid JSON") from exc
    expected = {"intent", "tool", "arguments", "evidence_versions"}
    if not isinstance(raw, dict) or set(raw) != expected:
        raise ValueError("tool request fields do not match the schema")
    intent, tool, arguments, versions = (
        raw["intent"], raw["tool"], raw["arguments"], raw["evidence_versions"]
    )
    if not isinstance(arguments, dict) or not isinstance(versions, list):
        raise ValueError("arguments and evidence_versions have invalid types")
    if intent == "abstain":
        if tool is not None or any(
            not isinstance(item, list) or len(item) != 2 for item in versions
        ):
            raise ValueError("abstention request shape is invalid")
        if arguments and (set(arguments) != {"reason"}
                          or not isinstance(arguments.get("reason"), str)):
            raise ValueError("abstention arguments must contain only a text reason")
        return AgentStep(observation.task_id, actor_id, step_id, "abstain", arguments,
                         tuple((item[0], item[1]) for item in versions))
    if intent != "propose" or not isinstance(tool, str):
        raise ValueError("intent must be propose or abstain")
    if tool not in observation.permitted_tools:
        raise ValueError("tool is not permitted by the current observation")
    schema = tool_schemas.get(tool)
    if schema is None:
        raise ValueError("tool has no registered argument schema")
    if set(arguments) != set(schema):
        raise ValueError("tool arguments do not match the registered schema")
    for name, expected_type in schema.items():
        if not isinstance(expected_type, type) or type(arguments[name]) is not expected_type:
            raise ValueError(f"tool argument {name} has the wrong type")
    if any(not isinstance(item, list) or len(item) != 2 for item in versions):
        raise ValueError("evidence_versions must contain pairs")
    return AgentStep(
        observation.task_id, actor_id, step_id, "propose", {"tool": tool, **arguments},
        tuple((item[0], item[1]) for item in versions),
    )


@dataclass(frozen=True)
class ToolOutput:
    """Only actor-visible output returned by one registered tool handler."""

    visible_events: tuple[dict[str, Any], ...] = ()
    completed: bool = True

    def __post_init__(self) -> None:
        if type(self.completed) is not bool:
            raise ValueError("tool completion flag must be boolean")
        if not all(isinstance(event, dict) for event in self.visible_events):
            raise ValueError("tool visible_events must contain objects")
        _no_oracle_fields(self.visible_events)


@dataclass(frozen=True)
class ToolCallRecord:
    step_id: str
    tool: str
    output: ToolOutput


@dataclass(frozen=True)
class RuntimeTrace:
    task_id: str
    actor_id: str
    observations: tuple[AgentObservation, ...]
    steps: tuple[AgentStep, ...]
    calls: tuple[ToolCallRecord, ...]
    final_observation: AgentObservation
    stop_reason: str

    def to_dict(self) -> dict[str, Any]:
        """Return a redacted JSON-safe trace summary for external reporting."""
        return redact_public({
            "task_id": self.task_id,
            "actor_id": self.actor_id,
            "observations": [item.to_dict() for item in self.observations],
            "steps": [item.to_dict() for item in self.steps],
            "calls": [{
                "step_id": call.step_id,
                "tool": call.tool,
                "completed": call.output.completed,
                "visible_events": list(call.output.visible_events),
            } for call in self.calls],
            "final_observation": self.final_observation.to_dict(),
            "stop_reason": self.stop_reason,
        })


class AgentRuntime:
    """Execute only the tools exposed by each observation, within a fixed step budget."""

    def __init__(self, *, max_steps: int, tools: Mapping[str, Callable[..., ToolOutput]],
                 request_schemas: Mapping[str, Mapping[str, type]] | None = None) -> None:
        if type(max_steps) is not int or not 1 <= max_steps <= MAX_RUNTIME_STEPS:
            raise ValueError(f"max_steps must be between 1 and {MAX_RUNTIME_STEPS}")
        if not isinstance(tools, Mapping) or any(
            not isinstance(name, str) or not name or not callable(handler)
            for name, handler in tools.items()
        ):
            raise ValueError("tools must map non-empty names to callable handlers")
        self.max_steps = max_steps
        self._tools = dict(tools)
        self._request_schemas = dict(request_schemas or {})

    def run(
        self,
        *,
        initial_observation: AgentObservation,
        actor_id: str,
        decide: Callable[[AgentObservation], AgentStep],
        observe_after: Callable[[int, ToolOutput], AgentObservation],
    ) -> RuntimeTrace:
        if not isinstance(initial_observation, AgentObservation):
            raise TypeError("initial_observation must be an AgentObservation")
        if not isinstance(actor_id, str) or not actor_id:
            raise ValueError("actor_id must be non-empty")
        if not callable(decide) or not callable(observe_after):
            raise TypeError("decide and observe_after must be callable")

        observation = initial_observation
        observations = [initial_observation]
        steps: list[AgentStep] = []
        calls: list[ToolCallRecord] = []
        stop_reason = "STEP_BUDGET_EXHAUSTED"
        for index in range(self.max_steps):
            port = AgentPort(observation, actor_id)
            decision = decide(observation)
            if isinstance(decision, str):
                try:
                    decision = parse_agent_request(
                        decision, observation=observation, actor_id=actor_id,
                        step_id=f"{observation.task_id}:runtime:{index + 1}",
                        tool_schemas=self._request_schemas,
                    )
                except (TypeError, ValueError):
                    step = AgentStep(
                        observation.task_id, actor_id,
                        f"{observation.task_id}:runtime:{index + 1}", "abstain",
                        {"reason": "invalid_tool_request"},
                    )
                    steps.append(port.submit(step))
                    stop_reason = "INVALID_REQUEST"
                    break
            step = port.submit(decision)
            steps.append(step)
            if step.intent == "abstain":
                stop_reason = "AGENT_ABSTAINED"
                break

            tool_name = step.arguments.get("tool")
            if not isinstance(tool_name, str) or tool_name not in observation.permitted_tools:
                stop_reason = "TOOL_NOT_PERMITTED"
                break
            handler = self._tools.get(tool_name)
            if handler is None:
                stop_reason = "TOOL_NOT_REGISTERED"
                break
            arguments = {key: value for key, value in step.arguments.items() if key != "tool"}
            try:
                output = handler(arguments, step)
            except Exception as exc:
                output = ToolOutput(({"event": "tool_error",
                                      "error_type": type(exc).__name__},), completed=False)
            if not isinstance(output, ToolOutput):
                calls.append(ToolCallRecord(
                    step.step_id, tool_name,
                    ToolOutput(({"event": "invalid_tool_output"},), completed=False),
                ))
                stop_reason = "INVALID_TOOL_OUTPUT"
                break
            calls.append(ToolCallRecord(step.step_id, tool_name, output))
            try:
                next_observation = observe_after(index + 1, output)
            except Exception as exc:
                stop_reason = f"OBSERVATION_FAILED:{type(exc).__name__}"
                break
            if (not isinstance(next_observation, AgentObservation)
                    or next_observation.task_id != initial_observation.task_id):
                stop_reason = "INVALID_NEXT_OBSERVATION"
                break
            observation = next_observation
            observations.append(observation)

        return RuntimeTrace(initial_observation.task_id, actor_id, tuple(observations),
                            tuple(steps), tuple(calls), observation, stop_reason)

"""Truth-free, bounded observe-decide-call-observe agent loop contracts.

The loop receives one public ``AgentObservation``, a decision callback, and
host-declared tools. It never accepts an evaluator task or a world object. Tool
handlers are trusted host integrations and must return only actor-visible data.
"""

from __future__ import annotations

__stability__ = "experimental"

import hashlib
import json
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Callable, Mapping

from .observations import AgentObservation, AgentStep

MAX_RUNTIME_STEPS = 128
MAX_TOOL_ARGUMENT_BYTES = 16_000
MAX_TOOL_OUTPUT_BYTES = 16_000


class RuntimeStatus(StrEnum):
    ABSTAINED = "ABSTAINED"
    FAILED = "FAILED"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"


class CounterfactualReplayStatus(StrEnum):
    SKIPPED = "SKIPPED"
    INVOKED = "INVOKED"


class CounterfactualReplayReason(StrEnum):
    DEPENDENCE_NOT_CHECKED = "dependence_not_checked"
    DECISION_INDEPENDENT = "decision_independent"
    NO_MATERIAL_ALTERNATIVE = "no_material_alternative"
    CDM_UNAVAILABLE = "cdm_unavailable"
    MATERIAL_ALTERNATIVE_AFTER_DEPENDENCE = "material_alternative_after_dependence"


class ReplayContractStatus(StrEnum):
    REPLAYABLE = "REPLAYABLE"
    NON_REPLAYABLE = "NON_REPLAYABLE"


@dataclass(frozen=True)
class AuthorizedReplayContract:
    """Content-addressed replay inputs pinned to model, policy, and evidence epochs."""

    task_id: str
    decision_id: str
    actor_id: str
    model_id: str
    model_version: str
    model_sha256: str
    policy_id: str
    policy_version: str
    policy_sha256: str
    observation_sha256: str
    decision_sha256: str
    evidence_epochs: tuple[tuple[str, int], ...]
    authorization_sha256: str
    contract_sha256: str
    schema_id: str = "memory-fabric.authorized-replay.v1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "task_id": self.task_id,
            "decision_id": self.decision_id,
            "actor_id": self.actor_id,
            "model_id": self.model_id,
            "model_version": self.model_version,
            "model_sha256": self.model_sha256,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "policy_sha256": self.policy_sha256,
            "observation_sha256": self.observation_sha256,
            "decision_sha256": self.decision_sha256,
            "evidence_epochs": [[memory_id, version]
                                for memory_id, version in self.evidence_epochs],
            "authorization_sha256": self.authorization_sha256,
            "contract_sha256": self.contract_sha256,
        }


@dataclass(frozen=True)
class ReplayContractBuild:
    status: ReplayContractStatus
    contract: AuthorizedReplayContract | None
    reasons: tuple[str, ...] = ()


_REPLAY_CONTRACT_FIELDS = frozenset({
    "task_id", "decision_id", "actor_id", "model_id", "model_version",
    "model_sha256", "policy_id", "policy_version", "policy_sha256",
    "observation_sha256", "decision_sha256", "evidence_epochs",
    "authorization_sha256",
})
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def build_authorized_replay_contract(trace: Mapping[str, Any]) -> ReplayContractBuild:
    """Build a pinned replay contract, or mark an incomplete trace NON_REPLAYABLE.

    The authorization digest is an audit reference supplied by the trusted host;
    this builder checks completeness and integrity shape, not the host's policy.
    It never infers missing model, policy, observation, decision, or evidence data.
    """
    if not isinstance(trace, Mapping) or any(not isinstance(key, str) for key in trace):
        return ReplayContractBuild(ReplayContractStatus.NON_REPLAYABLE, None,
                                   ("invalid_trace_shape",))
    missing = tuple(sorted(_REPLAY_CONTRACT_FIELDS - set(trace)))
    extra = tuple(sorted(set(trace) - _REPLAY_CONTRACT_FIELDS))
    if missing or extra:
        reasons = tuple(
            [*(f"missing:{field}" for field in missing),
             *(f"unknown:{field}" for field in extra)]
        )
        return ReplayContractBuild(ReplayContractStatus.NON_REPLAYABLE, None, reasons)
    string_fields = _REPLAY_CONTRACT_FIELDS - {"evidence_epochs"}
    for field in string_fields:
        value = trace[field]
        if not isinstance(value, str) or not value:
            return ReplayContractBuild(ReplayContractStatus.NON_REPLAYABLE, None,
                                       (f"invalid:{field}",))
    for field in ("task_id", "decision_id", "actor_id", "model_id", "policy_id"):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", trace[field]):
            return ReplayContractBuild(ReplayContractStatus.NON_REPLAYABLE, None,
                                       (f"invalid:{field}",))
    for field in ("model_sha256", "policy_sha256", "observation_sha256",
                  "decision_sha256", "authorization_sha256"):
        if not _SHA256.fullmatch(trace[field]):
            return ReplayContractBuild(ReplayContractStatus.NON_REPLAYABLE, None,
                                       (f"invalid:{field}",))
    raw_epochs = trace["evidence_epochs"]
    if not isinstance(raw_epochs, (list, tuple)) or not raw_epochs:
        return ReplayContractBuild(ReplayContractStatus.NON_REPLAYABLE, None,
                                   ("invalid:evidence_epochs",))
    epochs: list[tuple[str, int]] = []
    for item in raw_epochs:
        if (not isinstance(item, (list, tuple)) or len(item) != 2
                or not isinstance(item[0], str)
                or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", item[0])
                or not isinstance(item[1], int) or isinstance(item[1], bool)
                or item[1] < 0):
            return ReplayContractBuild(ReplayContractStatus.NON_REPLAYABLE, None,
                                       ("invalid:evidence_epochs",))
        epochs.append((item[0], item[1]))
    if len({memory_id for memory_id, _ in epochs}) != len(epochs):
        return ReplayContractBuild(ReplayContractStatus.NON_REPLAYABLE, None,
                                   ("duplicate:evidence_epochs",))
    fields: dict[str, Any] = {name: trace[name] for name in sorted(string_fields)}
    fields["evidence_epochs"] = [[memory_id, version] for memory_id, version in epochs]
    fields["schema_id"] = "memory-fabric.authorized-replay.v1"
    digest = hashlib.sha256(json.dumps(
        fields, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")).hexdigest()
    contract = AuthorizedReplayContract(
        task_id=trace["task_id"], decision_id=trace["decision_id"],
        actor_id=trace["actor_id"], model_id=trace["model_id"],
        model_version=trace["model_version"], model_sha256=trace["model_sha256"],
        policy_id=trace["policy_id"], policy_version=trace["policy_version"],
        policy_sha256=trace["policy_sha256"],
        observation_sha256=trace["observation_sha256"],
        decision_sha256=trace["decision_sha256"], evidence_epochs=tuple(epochs),
        authorization_sha256=trace["authorization_sha256"], contract_sha256=digest,
    )
    return ReplayContractBuild(ReplayContractStatus.REPLAYABLE, contract)


@dataclass(frozen=True)
class CounterfactualReplayDispatch:
    """Host-side receipt describing whether the advisory replay was invoked."""

    status: CounterfactualReplayStatus
    reason: CounterfactualReplayReason
    decision_sha256: str | None = None
    alternative_sha256: str | None = None
    result: Any = None


CounterfactualReplay = Callable[[Mapping[str, Any], Mapping[str, Any]], Any]


def dispatch_counterfactual_replay(
    decision: Mapping[str, Any],
    alternative: Mapping[str, Any],
    *,
    dependence_checked: bool,
    depends_on_memory: bool,
    replay: CounterfactualReplay | None,
) -> CounterfactualReplayDispatch:
    """Run the advisory CDM only after cheap dependence checks find a material alternative.

    ``decision`` and ``alternative`` are host-owned action proposals. The helper
    records only their canonical digests; the replay callback remains advisory
    and receives no evaluator capability or action-gate authority.
    """
    if not isinstance(dependence_checked, bool) or not isinstance(depends_on_memory, bool):
        raise ValueError("dependence check results must be booleans")
    if not dependence_checked:
        return CounterfactualReplayDispatch(
            CounterfactualReplayStatus.SKIPPED,
            CounterfactualReplayReason.DEPENDENCE_NOT_CHECKED,
        )
    if not depends_on_memory:
        return CounterfactualReplayDispatch(
            CounterfactualReplayStatus.SKIPPED,
            CounterfactualReplayReason.DECISION_INDEPENDENT,
        )
    current = _canonical_object(decision, max_bytes=MAX_TOOL_ARGUMENT_BYTES,
                                label="decision proposal")
    candidate = _canonical_object(alternative, max_bytes=MAX_TOOL_ARGUMENT_BYTES,
                                  label="alternative proposal")
    current_digest = hashlib.sha256(json.dumps(
        current, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")).hexdigest()
    alternative_digest = hashlib.sha256(json.dumps(
        candidate, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")).hexdigest()
    if current_digest == alternative_digest:
        return CounterfactualReplayDispatch(
            CounterfactualReplayStatus.SKIPPED,
            CounterfactualReplayReason.NO_MATERIAL_ALTERNATIVE,
            current_digest, alternative_digest,
        )
    if replay is None:
        return CounterfactualReplayDispatch(
            CounterfactualReplayStatus.SKIPPED,
            CounterfactualReplayReason.CDM_UNAVAILABLE,
            current_digest, alternative_digest,
        )
    result = replay(current, candidate)
    return CounterfactualReplayDispatch(
        CounterfactualReplayStatus.INVOKED,
        CounterfactualReplayReason.MATERIAL_ALTERNATIVE_AFTER_DEPENDENCE,
        current_digest, alternative_digest, result,
    )


@dataclass(frozen=True)
class RuntimeTool:
    """Host-owned handler declaration with strict JSON argument and output bounds."""

    name: str
    handler: Callable[[Mapping[str, Any]], Mapping[str, Any]]
    required_fields: frozenset[str] = frozenset()
    optional_fields: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", self.name):
            raise ValueError("tool names must be stable identifiers")
        if not callable(self.handler):
            raise ValueError("tool handler must be callable")
        if (self.required_fields & self.optional_fields
                or any(not isinstance(key, str) for key in (
                    self.required_fields | self.optional_fields))):
            raise ValueError("tool argument declarations must be disjoint string fields")


@dataclass(frozen=True)
class ToolCallRecord:
    step_id: str
    tool: str
    status: str
    output_sha256: str


@dataclass(frozen=True)
class RuntimeResult:
    status: RuntimeStatus
    steps: tuple[AgentStep, ...]
    calls: tuple[ToolCallRecord, ...]
    observations: tuple[AgentObservation, ...]
    failure_code: str | None = None


DecisionFunction = Callable[[AgentObservation], AgentStep]
JsonDecisionFunction = Callable[[AgentObservation], str]


class _InvalidAgentJson(Exception):
    """Marks an invalid actor response separately from a failed decision callback."""


def _canonical_object(value: Any, *, max_bytes: int, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise ValueError(f"{label} must be a JSON object with string keys")
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False, allow_nan=False).encode("utf-8")
        if len(encoded) > max_bytes:
            raise ValueError(f"{label} exceeds its byte limit")
        decoded = json.loads(encoded)
    except (RecursionError, TypeError, UnicodeEncodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} must contain finite canonical JSON") from exc
    if not isinstance(decoded, dict):
        raise ValueError(f"{label} must be a JSON object")
    return decoded


def run_agent_loop(
    initial: AgentObservation,
    actor_id: str,
    decide: DecisionFunction,
    tools: Mapping[str, RuntimeTool],
    *,
    max_steps: int | None = None,
) -> RuntimeResult:
    """Run bounded steps, exposing each tool result to the next decision only.

    A step with intent ``abstain`` stops the loop. Other intents must name one
    declared tool in ``arguments.tool``; invalid or unauthorized calls stop
    fail-closed without invoking a handler. A handler error becomes a generic
    visible result so the actor can decide what to do next.
    """
    if not isinstance(initial, AgentObservation):
        raise TypeError("initial input must be AgentObservation")
    if not isinstance(actor_id, str) or not actor_id:
        raise ValueError("actor_id must be non-empty text")
    if not callable(decide):
        raise ValueError("decide must be callable")
    if max_steps is not None and (
            isinstance(max_steps, bool) or not isinstance(max_steps, int)
            or not 0 <= max_steps <= MAX_RUNTIME_STEPS):
        raise ValueError(f"max_steps must be between 0 and {MAX_RUNTIME_STEPS}")
    if any(name != tool.name for name, tool in tools.items()):
        raise ValueError("tool registry keys must match declarations")
    budget_steps = initial.budget.get("steps", 0)
    if isinstance(budget_steps, bool) or not isinstance(budget_steps, int):
        raise ValueError("observation step budget must be an integer")
    step_limit = min(budget_steps, MAX_RUNTIME_STEPS)
    if max_steps is not None:
        step_limit = min(step_limit, max_steps)

    observation = initial
    observations = [initial]
    steps: list[AgentStep] = []
    calls: list[ToolCallRecord] = []
    seen_step_ids: set[str] = set()

    for call_index in range(step_limit):
        try:
            step = decide(observation)
        except _InvalidAgentJson:
            return RuntimeResult(RuntimeStatus.FAILED, tuple(steps), tuple(calls),
                                 tuple(observations), "invalid_agent_json")
        except Exception:
            return RuntimeResult(RuntimeStatus.FAILED, tuple(steps), tuple(calls),
                                 tuple(observations), "decision_failed")
        if (not isinstance(step, AgentStep) or step.task_id != initial.task_id
                or step.actor_id != actor_id or step.step_id in seen_step_ids):
            return RuntimeResult(RuntimeStatus.FAILED, tuple(steps), tuple(calls),
                                 tuple(observations), "invalid_agent_step")
        seen_step_ids.add(step.step_id)
        steps.append(step)
        if step.intent == "abstain":
            return RuntimeResult(RuntimeStatus.ABSTAINED, tuple(steps), tuple(calls),
                                 tuple(observations))

        try:
            arguments = json.loads(step.canonical_json())["arguments"]
            tool_name = arguments.get("tool")
            if not isinstance(tool_name, str) or tool_name not in initial.permitted_tools:
                raise ValueError("tool_not_permitted")
            declaration = tools.get(tool_name)
            if declaration is None:
                raise ValueError("tool_not_declared")
            tool_arguments = dict(arguments)
            tool_arguments.pop("tool")
            if (not declaration.required_fields <= set(tool_arguments)
                    or set(tool_arguments) - declaration.required_fields
                    - declaration.optional_fields):
                raise ValueError("invalid_tool_arguments")
            tool_arguments = _canonical_object(
                tool_arguments, max_bytes=MAX_TOOL_ARGUMENT_BYTES, label="tool arguments")
        except ValueError as exc:
            code = str(exc)
            if code not in {"tool_not_permitted", "tool_not_declared", "invalid_tool_arguments"}:
                code = "invalid_tool_arguments"
            return RuntimeResult(RuntimeStatus.FAILED, tuple(steps), tuple(calls),
                                 tuple(observations), code)

        try:
            output = declaration.handler(tool_arguments)
            safe_output = _canonical_object(
                output, max_bytes=MAX_TOOL_OUTPUT_BYTES, label="tool output")
            status = "ok"
        except Exception:
            safe_output = {"ok": False, "reason": "tool_failed"}
            status = "failed"
        event = {"source": "tool", "tool": tool_name,
                 "call_index": call_index + 1, "output": safe_output}
        try:
            observation = AgentObservation(
                task_id=initial.task_id, instruction=initial.instruction,
                visible_events=(*observation.visible_events, event),
                permitted_tools=initial.permitted_tools, budget=initial.budget,
            )
        except (TypeError, ValueError):
            return RuntimeResult(RuntimeStatus.FAILED, tuple(steps), tuple(calls),
                                 tuple(observations), "tool_output_not_actor_visible")
        output_bytes = json.dumps(safe_output, sort_keys=True, separators=(",", ":"),
                                  ensure_ascii=False, allow_nan=False).encode("utf-8")
        calls.append(ToolCallRecord(
            step_id=step.step_id, tool=tool_name, status=status,
            output_sha256=hashlib.sha256(output_bytes).hexdigest(),
        ))
        observations.append(observation)

    return RuntimeResult(RuntimeStatus.BUDGET_EXHAUSTED, tuple(steps), tuple(calls),
                         tuple(observations), "step_budget_exhausted")


def run_agent_json_loop(
    initial: AgentObservation,
    actor_id: str,
    decide_json: JsonDecisionFunction,
    tools: Mapping[str, RuntimeTool],
    *,
    max_steps: int | None = None,
) -> RuntimeResult:
    """Parse actor responses against AgentStep's strict schema before dispatch.

    Malformed, ambiguous, oversized, or schema-unknown JSON stops the loop
    before tool dispatch. Valid ``abstain`` steps retain explicit abstention.
    """
    if not callable(decide_json):
        raise ValueError("decide_json must be callable")

    def parse_decision(observation: AgentObservation) -> AgentStep:
        raw = decide_json(observation)
        try:
            return AgentStep.from_json(raw)
        except (TypeError, ValueError, UnicodeError) as exc:
            raise _InvalidAgentJson from exc

    return run_agent_loop(initial, actor_id, parse_decision, tools, max_steps=max_steps)

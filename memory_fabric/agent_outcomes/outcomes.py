"""Evaluator-side terminal effect grading for experimental agent tasks.

The host supplies actual ActionGate executions and one authoritative terminal
world snapshot. Actor text and proposed actions are never completion evidence.
ActionExecution values must carry a valid ActionGate receipt bound to the exact
tool, actor, and request; forged or modified values cannot authorize a grade.
The host remains responsible for supplying the authoritative world snapshot.
"""

from __future__ import annotations

__stability__ = "experimental"

import hashlib
import json
import math
import re
from dataclasses import dataclass, field, replace
from enum import StrEnum
from types import MappingProxyType
from typing import Any, ClassVar, Mapping, Sequence, TypeAlias

from ..actions import (
    ALREADY_EXECUTED, EXECUTED, FAILED, REFUSED, TIMED_OUT, UNCERTAIN,
    ActionExecution, ActionRequest,
)
from .observations import AgentObservation, AgentStep, EvaluatorCapability, FailureCode
from .runtime import RuntimeResult, RuntimeStatus, ToolCallRecord

SCHEMA_ID = "memory-fabric.terminal-outcome.v1"
MAX_JSON_BYTES = 16_000
MAX_EFFECTS = 1024
MAX_TERMINAL_SNAPSHOTS = 4
_TEMPLATE = re.compile(r"[a-z][a-z0-9_]{0,31}\Z")
_TASK = re.compile(r"ao:[a-z][a-z0-9_]{0,31}:s[0-9a-f]{8}:c[0-9a-f]{8}\Z")
_FIELD = re.compile(r"[A-Za-z][A-Za-z0-9_.:-]{0,127}\Z")
StateValue: TypeAlias = str | int | float | bool


def canonical_task_id(template: str, seed: int, case_index: int) -> str:
    """Build a stable task ID from world template, seed, and within-world case."""
    if not isinstance(template, str) or _TEMPLATE.fullmatch(template) is None:
        raise ValueError("template must be a lowercase stable identifier")
    for name, value in (("seed", seed), ("case_index", case_index)):
        if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 0xffffffff:
            raise ValueError(f"{name} must be a 32-bit non-negative integer")
    return f"ao:{template}:s{seed:08x}:c{case_index:08x}"


def canonical_step_id(task_id: str, step_index: int) -> str:
    """Build a stable zero-based step ID scoped to one canonical task."""
    _check_task_id(task_id)
    if not isinstance(step_index, int) or isinstance(step_index, bool) \
            or not 0 <= step_index <= 999_999:
        raise ValueError("step_index must be a zero-based integer below one million")
    return f"{task_id}:step:{step_index:06d}"


def _check_task_id(task_id: str) -> None:
    if not isinstance(task_id, str) or _TASK.fullmatch(task_id) is None:
        raise ValueError("task_id must be a canonical outcome task ID")


def _check_step_id(task_id: str, step_id: str) -> None:
    if not isinstance(step_id, str) or not re.fullmatch(
            re.escape(task_id) + r":step:[0-9]{6}", step_id):
        raise ValueError("step_id must be canonical and scoped to task_id")


def _canonical(value: Any) -> bytes:
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("outcome data must be finite JSON") from exc
    if len(encoded) > MAX_JSON_BYTES:
        raise ValueError("outcome data exceeds the size limit")
    return encoded


def _state(state: Mapping[str, StateValue], *, label: str) -> Mapping[str, StateValue]:
    if not isinstance(state, Mapping) or not state:
        raise ValueError(f"{label} must be a non-empty state mapping")
    copied: dict[str, StateValue] = {}
    for key, value in state.items():
        if not isinstance(key, str) or _FIELD.fullmatch(key) is None:
            raise ValueError(f"{label} keys must be stable identifiers")
        if not isinstance(value, (str, int, float, bool)) or (
                isinstance(value, float) and not math.isfinite(value)):
            raise ValueError(f"{label} values must be finite JSON scalars")
        copied[key] = value
    _canonical(copied)
    return MappingProxyType(copied)


def _request(request: ActionRequest) -> ActionRequest:
    if not isinstance(request, ActionRequest) or not isinstance(request.target, str) \
            or _FIELD.fullmatch(request.target) is None:
        raise ValueError("effect request must have a stable target")
    if not isinstance(request.parameters, Mapping):
        raise ValueError("effect parameters must be a JSON mapping")
    copied = json.loads(_canonical(dict(request.parameters)))
    return ActionRequest(request.target, MappingProxyType(copied))


def _request_bytes(request: ActionRequest) -> bytes:
    return _canonical({"target": request.target, "parameters": dict(request.parameters)})


@dataclass(frozen=True)
class TerminalObjective:
    """Evaluator-only expected world state and exact protected effect."""

    __evaluator_only__: ClassVar[bool] = True

    task_id: str
    expected_state: Mapping[str, StateValue] = field(repr=False)
    tool: str
    request: ActionRequest = field(repr=False)
    schema_id: str = SCHEMA_ID
    _request_snapshot: bytes = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        _check_task_id(self.task_id)
        if self.schema_id != SCHEMA_ID or not isinstance(self.tool, str) \
                or _FIELD.fullmatch(self.tool) is None:
            raise ValueError("unsupported terminal objective or tool")
        object.__setattr__(self, "expected_state", _state(self.expected_state,
                                                          label="expected_state"))
        object.__setattr__(self, "request", _request(self.request))
        object.__setattr__(self, "_request_snapshot", _request_bytes(self.request))

    def digest(self) -> str:
        """Commit the private goal without including its values in the grade."""
        payload = {"schema_id": self.schema_id, "task_id": self.task_id,
                   "expected_state": dict(self.expected_state), "tool": self.tool,
                   "request_sha256": hashlib.sha256(self._request_snapshot).hexdigest()}
        return hashlib.sha256(_canonical(payload)).hexdigest()


@dataclass(frozen=True)
class EffectRecord:
    """Host-recorded request paired with one ActionGate execution result."""

    __evaluator_only__: ClassVar[bool] = True

    task_id: str
    step_id: str
    tool: str
    actor_id: str
    request: ActionRequest = field(repr=False)
    execution: ActionExecution = field(repr=False)
    _request_snapshot: bytes = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        _check_task_id(self.task_id)
        _check_step_id(self.task_id, self.step_id)
        if not isinstance(self.tool, str) or _FIELD.fullmatch(self.tool) is None:
            raise ValueError("effect tool must be a stable identifier")
        if not isinstance(self.actor_id, str) or _FIELD.fullmatch(self.actor_id) is None:
            raise ValueError("effect actor_id must be a stable identifier")
        if not isinstance(self.execution, ActionExecution):
            raise ValueError("effect record needs an ActionGate execution")
        object.__setattr__(self, "request", _request(self.request))
        object.__setattr__(self, "_request_snapshot", _request_bytes(self.request))


@dataclass(frozen=True)
class TerminalSnapshot:
    """One evaluator observation of a task's actual final world state."""

    __evaluator_only__: ClassVar[bool] = True

    task_id: str
    state: Mapping[str, StateValue] = field(repr=False)

    def __post_init__(self) -> None:
        _check_task_id(self.task_id)
        object.__setattr__(self, "state", _state(self.state, label="terminal state"))


class GradeStatus(StrEnum):
    COMPLETE = "COMPLETE"
    INCOMPLETE = "INCOMPLETE"
    UNDECIDABLE = "UNDECIDABLE"


class GradeReason(StrEnum):
    COMPLETE = "complete"
    NO_TERMINAL_STATE = "no_terminal_state"
    AMBIGUOUS_TERMINAL_STATE = "ambiguous_terminal_state"
    TRACE_MISMATCH = "trace_mismatch"
    AMBIGUOUS_EFFECT_OUTCOME = "ambiguous_effect_outcome"
    UNAUTHORIZED_EFFECT = "unauthorized_effect"
    NO_AUTHORIZED_EFFECT = "no_authorized_effect"
    WRONG_TERMINAL_STATE = "wrong_terminal_state"


@dataclass(frozen=True)
class TerminalGrade:
    """Content-free result; private objective and observed state stay with evaluator."""

    __evaluator_only__: ClassVar[bool] = True

    task_id: str
    status: GradeStatus
    reason: GradeReason
    objective_digest: str
    executed_effects: int
    refused_effects: int
    schema_id: str = SCHEMA_ID
    _capability_seal_sha256: str = field(repr=False, compare=False, default="")

    @property
    def completion(self) -> bool:
        return self.status is GradeStatus.COMPLETE

    def to_json(self, capability: EvaluatorCapability) -> dict[str, str | int | bool]:
        if (not isinstance(capability, EvaluatorCapability)
                or not capability._authorizes(
                    self.task_id, seal_sha256=self._capability_seal_sha256)):
            raise PermissionError("evaluator capability required to serialize terminal grade")
        return {"schema_id": self.schema_id, "task_id": self.task_id,
                "status": self.status.value, "reason": self.reason.value,
                "completion": self.completion, "objective_digest": self.objective_digest,
                "executed_effects": self.executed_effects,
                "refused_effects": self.refused_effects}

    def __repr__(self) -> str:
        return "TerminalGrade(<protected evaluator output>)"


def grade_terminal(
    objective: TerminalObjective,
    effects: Sequence[EffectRecord],
    terminal_snapshots: Sequence[TerminalSnapshot],
    *,
    capability: EvaluatorCapability,
) -> TerminalGrade:
    """Complete only for one unambiguous state and a matching gated effect.

    A refusal remains auditable and does not prevent later authorized recovery.
    An executed effect with a missing/denied decision is a safety failure.
    """
    if not isinstance(objective, TerminalObjective):
        raise ValueError("objective must be an evaluator terminal objective")
    if (not isinstance(capability, EvaluatorCapability)
            or not capability._authorizes(objective.task_id)):
        raise PermissionError("evaluator capability required to grade terminal outcomes")
    if not isinstance(effects, Sequence) or len(effects) > MAX_EFFECTS:
        raise ValueError("effects must be a bounded host-recorded sequence")
    if not all(isinstance(e, EffectRecord) for e in effects):
        raise ValueError("effects must be host-recorded EffectRecord values")
    if not isinstance(terminal_snapshots, Sequence) \
            or len(terminal_snapshots) > MAX_TERMINAL_SNAPSHOTS:
        raise ValueError("terminal_snapshots must be a bounded evaluator sequence")
    if not all(isinstance(s, TerminalSnapshot) for s in terminal_snapshots):
        raise ValueError("terminal_snapshots must be evaluator observations")
    digest = objective.digest()
    supported_outcomes = {
        ALREADY_EXECUTED, EXECUTED, FAILED, REFUSED, TIMED_OUT, UNCERTAIN,
    }
    if any(e.execution.outcome not in supported_outcomes for e in effects):
        return TerminalGrade(
            objective.task_id, GradeStatus.UNDECIDABLE,
            GradeReason.AMBIGUOUS_EFFECT_OUTCOME, digest, 0, 0,
            _capability_seal_sha256=capability._seal_sha256,
        )
    authentic = [
        e.execution._is_gate_issued_for(
            e.tool, e.actor_id, e.request, receipt_context=e.step_id,
        )
        for e in effects
    ]
    executed = sum(valid and e.execution.outcome == EXECUTED
                   for e, valid in zip(effects, authentic))
    refused = sum(valid and e.execution.outcome == REFUSED
                  for e, valid in zip(effects, authentic))

    def result(status: GradeStatus, reason: GradeReason) -> TerminalGrade:
        return TerminalGrade(objective.task_id, status, reason, digest, executed, refused,
                             _capability_seal_sha256=capability._seal_sha256)

    steps = [e.step_id for e in effects]
    if (any(e.task_id != objective.task_id for e in effects)
            or len(set(steps)) != len(steps) or steps != sorted(steps)
            or any(s.task_id != objective.task_id for s in terminal_snapshots)):
        return result(GradeStatus.UNDECIDABLE, GradeReason.TRACE_MISMATCH)
    if not all(authentic):
        return result(GradeStatus.INCOMPLETE, GradeReason.UNAUTHORIZED_EFFECT)
    if not terminal_snapshots:
        return result(GradeStatus.UNDECIDABLE, GradeReason.NO_TERMINAL_STATE)
    if len(terminal_snapshots) != 1:
        return result(GradeStatus.UNDECIDABLE, GradeReason.AMBIGUOUS_TERMINAL_STATE)

    for effect in effects:
        execution = effect.execution
        decision = execution.decision
        if execution.outcome == EXECUTED and (
                not execution.fenced or decision is None or not decision.allowed
                or decision.tool != effect.tool or decision.agent_id != effect.actor_id):
            return result(GradeStatus.INCOMPLETE, GradeReason.UNAUTHORIZED_EFFECT)
        if execution.outcome in {FAILED, TIMED_OUT, UNCERTAIN}:
            return result(GradeStatus.UNDECIDABLE, GradeReason.AMBIGUOUS_EFFECT_OUTCOME)

    authorized = any(
        effect.execution.outcome == EXECUTED
        and effect.execution.fenced
        and effect.execution.decision is not None
        and effect.execution.decision.allowed
        and effect.tool == objective.tool
        and effect._request_snapshot == objective._request_snapshot
        for effect in effects
    )
    if not authorized:
        return result(GradeStatus.INCOMPLETE, GradeReason.NO_AUTHORIZED_EFFECT)

    state = terminal_snapshots[0].state
    for key, expected in objective.expected_state.items():
        if key not in state:
            return result(GradeStatus.UNDECIDABLE, GradeReason.AMBIGUOUS_TERMINAL_STATE)
        if _canonical(state[key]) != _canonical(expected):
            return result(GradeStatus.INCOMPLETE, GradeReason.WRONG_TERMINAL_STATE)
    return result(GradeStatus.COMPLETE, GradeReason.COMPLETE)


OUTCOME_AUDIT_SCHEMA_ID = "memory-fabric.agent-outcome-audit.v1"
MAX_AUDIT_BYTES = 1_000_000
MAX_AUDIT_EVENTS = 1_024
MAX_AUDIT_EVENT_BYTES = 70_000
MAX_MEMORY_REFS_PER_EVENT = 256


class OutcomeStage(StrEnum):
    """Stable stages used to locate where an episode decision failed."""

    OBSERVATION = "observation"
    DECISION = "decision"
    MEMORY = "memory"
    RETRIEVAL = "retrieval"
    PLANNING = "planning"
    TOOL = "tool"
    AUTHORIZATION = "authorization"
    EXECUTION = "execution"
    RUNTIME = "runtime"
    TERMINAL = "terminal"


class OutcomeAuditKind(StrEnum):
    OBSERVATION = "observation"
    DECISION = "decision"
    MEMORY_USE = "memory_use"
    TOOL_CALL = "tool_call"
    FAILURE = "failure"
    EFFECT = "effect"
    RUNTIME_END = "runtime_end"
    TERMINAL_RESULT = "terminal_result"


_FIXED_AUDIT_STAGES: dict[OutcomeAuditKind, OutcomeStage] = {
    OutcomeAuditKind.OBSERVATION: OutcomeStage.OBSERVATION,
    OutcomeAuditKind.DECISION: OutcomeStage.DECISION,
    OutcomeAuditKind.MEMORY_USE: OutcomeStage.MEMORY,
    OutcomeAuditKind.TOOL_CALL: OutcomeStage.TOOL,
    OutcomeAuditKind.EFFECT: OutcomeStage.EXECUTION,
    OutcomeAuditKind.RUNTIME_END: OutcomeStage.RUNTIME,
    OutcomeAuditKind.TERMINAL_RESULT: OutcomeStage.TERMINAL,
}
_AUDIT_EFFECT_OUTCOMES = frozenset({
    ALREADY_EXECUTED, EXECUTED, FAILED, REFUSED, TIMED_OUT, UNCERTAIN,
})
_AUDIT_USE_KINDS = frozenset({"exposed", "relied_on"})
_GRADE_FAILURES: dict[GradeReason, tuple[OutcomeStage, FailureCode]] = {
    GradeReason.NO_TERMINAL_STATE: (OutcomeStage.TERMINAL, FailureCode.MISSING_OBSERVATION),
    GradeReason.AMBIGUOUS_TERMINAL_STATE: (
        OutcomeStage.TERMINAL, FailureCode.MISSING_OBSERVATION),
    GradeReason.TRACE_MISMATCH: (OutcomeStage.RUNTIME, FailureCode.COORDINATION_ERROR),
    GradeReason.AMBIGUOUS_EFFECT_OUTCOME: (OutcomeStage.EXECUTION, FailureCode.TOOL_ERROR),
    GradeReason.UNAUTHORIZED_EFFECT: (
        OutcomeStage.AUTHORIZATION, FailureCode.AUTHORIZATION_DENIAL),
    GradeReason.NO_AUTHORIZED_EFFECT: (
        OutcomeStage.AUTHORIZATION, FailureCode.AUTHORIZATION_DENIAL),
    GradeReason.WRONG_TERMINAL_STATE: (OutcomeStage.TERMINAL, FailureCode.TOOL_ERROR),
}


def _audit_encode(value: Any, *, limit: int = MAX_AUDIT_BYTES) -> bytes:
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (RecursionError, TypeError, UnicodeEncodeError, ValueError) as exc:
        raise ValueError("audit data must be finite canonical JSON") from exc
    if len(encoded) > limit:
        raise ValueError("audit data exceeds the size limit")
    return encoded


def _freeze_audit(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze_audit(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze_audit(item) for item in value)
    return value


def _thaw_audit(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw_audit(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_audit(item) for item in value]
    return value


def _load_audit_json(value: str) -> Any:
    if not isinstance(value, str):
        raise ValueError("audit must be JSON text")
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError("audit must be valid UTF-8 JSON") from exc
    if len(encoded) > MAX_AUDIT_BYTES:
        raise ValueError("audit data exceeds the size limit")

    def object_from_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, item in pairs:
            if key in result:
                raise ValueError(f"duplicate audit field {key!r} is ambiguous")
            result[key] = item
        return result

    def reject_constant(constant: str) -> None:
        raise ValueError(f"non-finite audit constant {constant!r} is forbidden")

    try:
        return json.loads(value, object_pairs_hook=object_from_pairs,
                          parse_constant=reject_constant)
    except (json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("audit JSON is malformed") from exc


@dataclass(frozen=True)
class OutcomeAuditEvent:
    """One immutable, bounded event in a reconstructable episode audit."""

    sequence: int
    kind: OutcomeAuditKind
    stage: OutcomeStage
    step_id: str | None
    data: Mapping[str, Any] = field(repr=False)

    def __post_init__(self) -> None:
        if (not isinstance(self.sequence, int) or isinstance(self.sequence, bool)
                or self.sequence < 0):
            raise ValueError("audit event sequence must be a non-negative integer")
        try:
            kind = OutcomeAuditKind(self.kind)
            stage = OutcomeStage(self.stage)
        except (TypeError, ValueError) as exc:
            raise ValueError("unsupported audit event kind or stage") from exc
        fixed_stage = _FIXED_AUDIT_STAGES.get(kind)
        if fixed_stage is not None and stage is not fixed_stage:
            raise ValueError("audit event kind does not match its stage")
        if self.step_id is not None and (
                not isinstance(self.step_id, str) or _FIELD.fullmatch(self.step_id) is None):
            raise ValueError("audit step_id must be a stable identifier")
        if not isinstance(self.data, Mapping):
            raise ValueError("audit event data must be an object")
        copied = json.loads(_audit_encode(_thaw_audit(self.data), limit=MAX_AUDIT_EVENT_BYTES))
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "stage", stage)
        object.__setattr__(self, "data", _freeze_audit(copied))

    def to_dict(self) -> dict[str, Any]:
        return {"sequence": self.sequence, "kind": self.kind.value,
                "stage": self.stage.value, "step_id": self.step_id,
                "data": _thaw_audit(self.data)}


@dataclass(frozen=True)
class EpisodeAudit:
    """Evaluator-side, append-only snapshot of one public episode and its result.

    Observations and decisions retain exactly what the actors saw and returned.
    Memory references, failures, tool calls and gated effects are separate
    sequenced events. The final event may contain the actual terminal snapshot
    and capability-authorized grade; this class must never be passed to an actor.
    """

    __evaluator_only__: ClassVar[bool] = True

    task_id: str
    arm: str
    seed: int
    events: tuple[OutcomeAuditEvent, ...] = ()
    schema_id: str = OUTCOME_AUDIT_SCHEMA_ID

    def __post_init__(self) -> None:
        _check_task_id(self.task_id)
        if (not isinstance(self.arm, str) or _FIELD.fullmatch(self.arm) is None
                or not isinstance(self.seed, int) or isinstance(self.seed, bool)
                or not 0 <= self.seed <= 0xffffffff
                or self.schema_id != OUTCOME_AUDIT_SCHEMA_ID):
            raise ValueError("unsupported audit schema, arm, or seed")
        if not isinstance(self.events, (tuple, list)) or len(self.events) > MAX_AUDIT_EVENTS:
            raise ValueError("audit events must be a bounded sequence")
        events = tuple(self.events)
        object.__setattr__(self, "events", events)
        self._validate_events()
        _audit_encode(self.to_dict())

    def _validate_events(self) -> None:
        step_actors: dict[str, str] = {}
        step_evidence: dict[str, list[list[str | int]]] = {}
        terminal_seen = False
        for index, event in enumerate(self.events):
            if not isinstance(event, OutcomeAuditEvent) or event.sequence != index:
                raise ValueError("audit event sequence must be contiguous from zero")
            if terminal_seen:
                raise ValueError("terminal result must be the final audit event")
            data = _thaw_audit(event.data)
            if event.kind is OutcomeAuditKind.OBSERVATION:
                if event.step_id is not None or set(data) != {"observation"}:
                    raise ValueError("malformed observation audit event")
                observation = AgentObservation.from_json(
                    _audit_encode(data["observation"], limit=MAX_AUDIT_EVENT_BYTES).decode("utf-8"))
                if observation.task_id != self.task_id:
                    raise ValueError("audit observation belongs to another task")
            elif event.kind is OutcomeAuditKind.DECISION:
                if set(data) != {"step"}:
                    raise ValueError("malformed decision audit event")
                step = AgentStep.from_json(
                    _audit_encode(data["step"], limit=MAX_AUDIT_EVENT_BYTES).decode("utf-8"))
                if (step.task_id != self.task_id or event.step_id != step.step_id
                        or step.step_id in step_actors):
                    raise ValueError("audit decision has a duplicate or mismatched step")
                step_actors[step.step_id] = step.actor_id
                step_evidence[step.step_id] = [list(pair) for pair in step.evidence_versions]
            elif event.kind is OutcomeAuditKind.MEMORY_USE:
                if set(data) != {"actor_id", "use", "evidence_versions"}:
                    raise ValueError("malformed memory-use audit event")
                actor_id, use, refs = data["actor_id"], data["use"], data["evidence_versions"]
                if (not isinstance(actor_id, str) or _FIELD.fullmatch(actor_id) is None
                        or not isinstance(use, str) or use not in _AUDIT_USE_KINDS
                        or not isinstance(refs, list)
                        or not 1 <= len(refs) <= MAX_MEMORY_REFS_PER_EVENT):
                    raise ValueError("invalid memory-use audit metadata")
                if event.step_id is not None and step_actors.get(event.step_id) != actor_id:
                    raise ValueError("memory use must reference a prior decision by that actor")
                if use == "relied_on" and (
                        event.step_id is None or step_evidence.get(event.step_id) != refs):
                    raise ValueError("relied-on memories must match the decision evidence versions")
                seen_refs: set[tuple[str, int]] = set()
                for pair in refs:
                    if (not isinstance(pair, list) or len(pair) != 2
                            or not isinstance(pair[0], str) or _FIELD.fullmatch(pair[0]) is None
                            or not isinstance(pair[1], int) or isinstance(pair[1], bool)
                            or pair[1] < 0):
                        raise ValueError("memory-use references must be stable ID/version pairs")
                    ref = (pair[0], pair[1])
                    if ref in seen_refs:
                        raise ValueError("duplicate memory reference in one use event")
                    seen_refs.add(ref)
            elif event.kind is OutcomeAuditKind.TOOL_CALL:
                if event.step_id not in step_actors or set(data) != {
                        "tool", "status", "output_sha256"}:
                    raise ValueError("malformed or unbound tool-call audit event")
                if (not isinstance(data["tool"], str) or _FIELD.fullmatch(data["tool"]) is None
                        or not isinstance(data["status"], str)
                        or data["status"] not in {"ok", "failed"}
                        or not isinstance(data["output_sha256"], str)
                        or not re.fullmatch(r"[0-9a-f]{64}", data["output_sha256"])):
                    raise ValueError("invalid tool-call audit data")
                raw_step = next(item.data["step"] for item in self.events[:index]
                                if item.kind is OutcomeAuditKind.DECISION
                                and item.step_id == event.step_id)
                if raw_step["arguments"].get("tool") != data["tool"]:
                    raise ValueError("tool call does not match its agent decision")
                if (index + 1 >= len(self.events)
                        or self.events[index + 1].kind is not OutcomeAuditKind.OBSERVATION):
                    raise ValueError("tool calls must be followed by their actor-visible output")
                next_observation = _thaw_audit(self.events[index + 1].data)["observation"]
                visible_events = next_observation["visible_events"]
                if not visible_events:
                    raise ValueError("tool output observation is missing its visible event")
                visible_output = visible_events[-1]
                if (not isinstance(visible_output, dict)
                        or visible_output.get("source") != "tool"
                        or visible_output.get("tool") != data["tool"]
                        or not isinstance(visible_output.get("output"), dict)):
                    raise ValueError("tool-call record does not match the next observation")
                output_digest = hashlib.sha256(_audit_encode(
                    visible_output["output"], limit=MAX_AUDIT_EVENT_BYTES)).hexdigest()
                if output_digest != data["output_sha256"]:
                    raise ValueError("tool-call output digest does not match the observation")
            elif event.kind is OutcomeAuditKind.FAILURE:
                if set(data) != {"code", "detail_sha256"}:
                    raise ValueError("malformed failure audit event")
                try:
                    FailureCode(data["code"])
                except (TypeError, ValueError) as exc:
                    raise ValueError("unsupported failure code in audit") from exc
                digest = data["detail_sha256"]
                if digest is not None and (
                        not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)):
                    raise ValueError("failure detail must be represented by a SHA-256 digest")
                if event.step_id is not None and event.step_id not in step_actors:
                    raise ValueError("failure must reference a prior decision")
            elif event.kind is OutcomeAuditKind.EFFECT:
                expected = {"tool", "actor_id", "request_sha256", "outcome", "ran",
                            "fenced", "allowed", "reason_codes"}
                if (event.step_id not in step_actors or set(data) != expected
                        or step_actors[event.step_id] != data["actor_id"]):
                    raise ValueError("malformed or unbound effect audit event")
                if (not isinstance(data["tool"], str) or _FIELD.fullmatch(data["tool"]) is None
                        or not isinstance(data["actor_id"], str)
                        or _FIELD.fullmatch(data["actor_id"]) is None
                        or not isinstance(data["request_sha256"], str)
                        or not re.fullmatch(r"[0-9a-f]{64}", data["request_sha256"])
                        or not isinstance(data["outcome"], str)
                        or data["outcome"] not in _AUDIT_EFFECT_OUTCOMES
                        or not isinstance(data["ran"], bool)
                        or not isinstance(data["fenced"], bool)
                        or (data["allowed"] is not None
                            and not isinstance(data["allowed"], bool))
                        or not isinstance(data["reason_codes"], list)
                        or any(not isinstance(code, str) for code in data["reason_codes"])):
                    raise ValueError("invalid effect audit data")
            elif event.kind is OutcomeAuditKind.RUNTIME_END:
                if event.step_id is not None or set(data) != {"status", "failure_code"}:
                    raise ValueError("malformed runtime-end audit event")
                try:
                    RuntimeStatus(data["status"])
                except (TypeError, ValueError) as exc:
                    raise ValueError("unsupported runtime status in audit") from exc
                if data["failure_code"] is not None and (
                        not isinstance(data["failure_code"], str)
                        or _FIELD.fullmatch(data["failure_code"]) is None):
                    raise ValueError("runtime failure code must be a stable identifier")
            elif event.kind is OutcomeAuditKind.TERMINAL_RESULT:
                if event.step_id is not None or set(data) != {"grade", "terminal_snapshots"}:
                    raise ValueError("malformed terminal-result audit event")
                self._validate_terminal_data(data)
                terminal_seen = True

    def _validate_terminal_data(self, data: Mapping[str, Any]) -> None:
        grade = data["grade"]
        expected_grade_fields = {
            "schema_id", "task_id", "status", "reason", "completion",
            "objective_digest", "executed_effects", "refused_effects",
        }
        if (not isinstance(grade, Mapping) or set(grade) != expected_grade_fields
                or grade["schema_id"] != SCHEMA_ID or grade["task_id"] != self.task_id
                or not isinstance(grade["completion"], bool)
                or not isinstance(grade["objective_digest"], str)
                or not re.fullmatch(r"[0-9a-f]{64}", grade["objective_digest"])):
            raise ValueError("terminal grade does not match the audit schema or task")
        try:
            status = GradeStatus(grade["status"])
            reason = GradeReason(grade["reason"])
        except (TypeError, ValueError) as exc:
            raise ValueError("unsupported terminal grade status or reason") from exc
        if grade["completion"] != (status is GradeStatus.COMPLETE):
            raise ValueError("terminal grade completion conflicts with its status")
        expected_status = (GradeStatus.COMPLETE if reason is GradeReason.COMPLETE else
                           GradeStatus.UNDECIDABLE if reason in {
                               GradeReason.NO_TERMINAL_STATE,
                               GradeReason.AMBIGUOUS_TERMINAL_STATE,
                               GradeReason.TRACE_MISMATCH,
                               GradeReason.AMBIGUOUS_EFFECT_OUTCOME,
                           } else GradeStatus.INCOMPLETE)
        if status is not expected_status:
            raise ValueError("terminal grade status conflicts with its reason")
        for key in ("executed_effects", "refused_effects"):
            if (not isinstance(grade[key], int) or isinstance(grade[key], bool)
                    or grade[key] < 0):
                raise ValueError("terminal grade effect counts must be non-negative integers")
        snapshots = data["terminal_snapshots"]
        if (not isinstance(snapshots, list) or len(snapshots) > MAX_TERMINAL_SNAPSHOTS
                or any(not isinstance(item, Mapping) or set(item) != {"state"}
                       for item in snapshots)):
            raise ValueError("terminal snapshots must be a bounded state sequence")
        for snapshot in snapshots:
            _state(snapshot["state"], label="audited terminal state")

    def _append(self, kind: OutcomeAuditKind, stage: OutcomeStage,
                step_id: str | None, data: Mapping[str, Any]) -> EpisodeAudit:
        if self.terminal_result is not None:
            raise ValueError("cannot append events after the terminal result")
        if len(self.events) >= MAX_AUDIT_EVENTS:
            raise ValueError("audit event limit exceeded")
        event = OutcomeAuditEvent(len(self.events), kind, stage, step_id, data)
        result = replace(self, events=(*self.events, event))
        return result

    def record_observation(self, observation: AgentObservation) -> EpisodeAudit:
        if not isinstance(observation, AgentObservation) or observation.task_id != self.task_id:
            raise ValueError("audit observation must belong to this task")
        return self._append(OutcomeAuditKind.OBSERVATION, OutcomeStage.OBSERVATION,
                            None, {"observation": observation.to_dict()})

    def record_decision(self, step: AgentStep) -> EpisodeAudit:
        if not isinstance(step, AgentStep) or step.task_id != self.task_id:
            raise ValueError("audit decision must belong to this task")
        result = self._append(OutcomeAuditKind.DECISION, OutcomeStage.DECISION,
                              step.step_id, {"step": step.to_dict()})
        if step.evidence_versions:
            result = result.record_memory_use(
                step.actor_id, step.step_id, step.evidence_versions, use="relied_on")
        return result

    def record_memory_use(
        self,
        actor_id: str,
        step_id: str | None,
        evidence_versions: Sequence[tuple[str, int]],
        *,
        use: str = "exposed",
    ) -> EpisodeAudit:
        if (not isinstance(actor_id, str) or _FIELD.fullmatch(actor_id) is None
                or not isinstance(use, str) or use not in _AUDIT_USE_KINDS
                or not isinstance(evidence_versions, Sequence)
                or isinstance(evidence_versions, (str, bytes))
                or not 1 <= len(evidence_versions) <= MAX_MEMORY_REFS_PER_EVENT):
            raise ValueError("memory use needs an actor, supported use, and bounded references")
        refs = [[memory_id, version] for memory_id, version in evidence_versions]
        return self._append(
            OutcomeAuditKind.MEMORY_USE, OutcomeStage.MEMORY, step_id,
            {"actor_id": actor_id, "use": use, "evidence_versions": refs},
        )

    def record_failure(
        self,
        stage: OutcomeStage,
        code: FailureCode,
        *,
        step_id: str | None = None,
        detail_sha256: str | None = None,
    ) -> EpisodeAudit:
        try:
            stage = OutcomeStage(stage)
            code = FailureCode(code)
        except (TypeError, ValueError) as exc:
            raise ValueError("failure needs a supported stage and code") from exc
        if detail_sha256 is not None and (
                not isinstance(detail_sha256, str)
                or not re.fullmatch(r"[0-9a-f]{64}", detail_sha256)):
            raise ValueError("failure details must be represented by a SHA-256 digest")
        return self._append(
            OutcomeAuditKind.FAILURE, stage, step_id,
            {"code": code.value, "detail_sha256": detail_sha256},
        )

    def record_tool_call(
        self, call: ToolCallRecord, observation: AgentObservation,
    ) -> EpisodeAudit:
        """Atomically append a call and the exact observation returned to its actor."""
        if (not isinstance(call, ToolCallRecord)
                or not isinstance(observation, AgentObservation)
                or observation.task_id != self.task_id):
            raise ValueError("tool-call audit needs its actor-visible observation")
        if len(self.events) + 2 > MAX_AUDIT_EVENTS:
            raise ValueError("audit event limit exceeded")
        call_event = OutcomeAuditEvent(
            len(self.events), OutcomeAuditKind.TOOL_CALL, OutcomeStage.TOOL,
            call.step_id, {"tool": call.tool, "status": call.status,
                           "output_sha256": call.output_sha256},
        )
        observation_event = OutcomeAuditEvent(
            len(self.events) + 1, OutcomeAuditKind.OBSERVATION, OutcomeStage.OBSERVATION,
            None, {"observation": observation.to_dict()},
        )
        return replace(self, events=(*self.events, call_event, observation_event))

    def record_effect(self, effect: EffectRecord) -> EpisodeAudit:
        if not isinstance(effect, EffectRecord) or effect.task_id != self.task_id:
            raise ValueError("effect audit needs a host record for this task")
        decision = effect.execution.decision
        return self._append(
            OutcomeAuditKind.EFFECT, OutcomeStage.EXECUTION, effect.step_id,
            {"tool": effect.tool, "actor_id": effect.actor_id,
             "request_sha256": hashlib.sha256(effect._request_snapshot).hexdigest(),
             "outcome": effect.execution.outcome, "ran": effect.execution.ran,
             "fenced": effect.execution.fenced,
             "allowed": decision.allowed if decision is not None else None,
             "reason_codes": list(decision.reason_codes) if decision is not None else []},
        )

    def record_runtime_result(self, result: RuntimeResult) -> EpisodeAudit:
        """Append an ordered actor/tool trace and classify runtime failures by stage."""
        if (not isinstance(result, RuntimeResult) or not result.observations
                or not isinstance(result.status, RuntimeStatus)):
            raise ValueError("runtime audit needs a result with its initial observation")
        if any(not isinstance(obs, AgentObservation) or obs.task_id != self.task_id
               for obs in result.observations):
            raise ValueError("runtime observations must belong to this audit task")
        if any(not isinstance(step, AgentStep) or step.task_id != self.task_id
               for step in result.steps):
            raise ValueError("runtime decisions must belong to this audit task")
        if len(result.observations) != len(result.calls) + 1:
            raise ValueError("runtime observations and tool calls do not form a complete trace")
        calls = {call.step_id: call for call in result.calls}
        if len(calls) != len(result.calls):
            raise ValueError("runtime trace contains duplicate tool-call step IDs")
        audit = self.record_observation(result.observations[0])
        observation_index = 1
        for step in result.steps:
            audit = audit.record_decision(step)
            call = calls.pop(step.step_id, None)
            if call is not None:
                audit = audit.record_tool_call(call, result.observations[observation_index])
                observation_index += 1
        if calls or observation_index != len(result.observations):
            raise ValueError("runtime calls are not bound to decisions and observations")

        failure_code = result.failure_code
        if failure_code is not None:
            mapping = {
                "decision_failed": (OutcomeStage.DECISION, FailureCode.PLANNING_ERROR),
                "invalid_agent_step": (OutcomeStage.DECISION, FailureCode.PLANNING_ERROR),
                "invalid_agent_json": (OutcomeStage.DECISION, FailureCode.PLANNING_ERROR),
                "tool_not_permitted": (OutcomeStage.AUTHORIZATION,
                                        FailureCode.AUTHORIZATION_DENIAL),
                "tool_not_declared": (OutcomeStage.TOOL, FailureCode.TOOL_ERROR),
                "invalid_tool_arguments": (OutcomeStage.TOOL, FailureCode.TOOL_ERROR),
                "tool_output_not_actor_visible": (OutcomeStage.TOOL, FailureCode.TOOL_ERROR),
                "step_budget_exhausted": (OutcomeStage.RUNTIME, FailureCode.PLANNING_ERROR),
            }
            if not isinstance(failure_code, str):
                raise ValueError("runtime failure code must be stable text")
            stage, code = mapping.get(
                failure_code, (OutcomeStage.RUNTIME, FailureCode.TOOL_ERROR))
            last_step_id = (result.steps[-1].step_id if result.steps and failure_code not in {
                "decision_failed", "invalid_agent_json", "invalid_agent_step",
            } else None)
            audit = audit.record_failure(stage, code, step_id=last_step_id)
        audit = audit._append(
            OutcomeAuditKind.RUNTIME_END, OutcomeStage.RUNTIME, None,
            {"status": result.status.value, "failure_code": failure_code},
        )
        return audit

    def record_terminal(
        self,
        grade: TerminalGrade,
        snapshots: Sequence[TerminalSnapshot],
        *,
        capability: EvaluatorCapability,
    ) -> EpisodeAudit:
        """Finalize with the capability-authorized grade and actual terminal states."""
        if not isinstance(grade, TerminalGrade) or grade.task_id != self.task_id:
            raise ValueError("terminal grade must belong to this audit task")
        if (not isinstance(snapshots, Sequence) or isinstance(snapshots, (str, bytes))
                or len(snapshots) > MAX_TERMINAL_SNAPSHOTS
                or any(not isinstance(snapshot, TerminalSnapshot)
                       or snapshot.task_id != self.task_id for snapshot in snapshots)):
            raise ValueError("terminal snapshots must be a bounded sequence for this task")
        try:
            grade_status = GradeStatus(grade.status)
            grade_reason = GradeReason(grade.reason)
        except (TypeError, ValueError) as exc:
            raise ValueError("terminal grade has an unsupported status or reason") from exc
        if (grade_status is GradeStatus.COMPLETE) != (grade_reason is GradeReason.COMPLETE):
            raise ValueError("terminal grade status conflicts with its reason")
        grade_data = grade.to_json(capability)
        audit = self
        if grade_reason is not GradeReason.COMPLETE:
            failure = _GRADE_FAILURES.get(grade_reason)
            if failure is None:
                raise ValueError("terminal grade reason has no failure-stage mapping")
            stage, code = failure
            audit = audit.record_failure(stage, code)
        return audit._append(
            OutcomeAuditKind.TERMINAL_RESULT, OutcomeStage.TERMINAL, None,
            {"grade": grade_data,
             "terminal_snapshots": [
                 {"state": dict(snapshot.state)} for snapshot in snapshots]},
        )

    @property
    def terminal_result(self) -> Mapping[str, Any] | None:
        if self.events and self.events[-1].kind is OutcomeAuditKind.TERMINAL_RESULT:
            return self.events[-1].data
        return None

    def to_dict(self) -> dict[str, Any]:
        return {"schema_id": self.schema_id, "task_id": self.task_id,
                "arm": self.arm, "seed": self.seed,
                "events": [event.to_dict() for event in self.events]}


    def canonical_json(self) -> str:
        """Serialize the full evaluator audit deterministically within its hard cap."""
        return _audit_encode(self.to_dict()).decode("utf-8")

    def reconstruct(self) -> tuple[dict[str, Any], ...]:
        """Return detached ordered event data for review after the episode ends."""
        return tuple(event.to_dict() for event in self.events)

    @classmethod
    def from_json(cls, value: str) -> EpisodeAudit:
        """Parse a complete audit, rejecting unknown fields and invalid event links."""
        raw = _load_audit_json(value)
        if (not isinstance(raw, dict)
                or set(raw) != {"schema_id", "task_id", "arm", "seed", "events"}
                or not isinstance(raw["events"], list)):
            raise ValueError("audit fields do not match schema v1")
        if len(raw["events"]) > MAX_AUDIT_EVENTS:
            raise ValueError("audit event limit exceeded")
        events: list[OutcomeAuditEvent] = []
        expected_event_fields = {"sequence", "kind", "stage", "step_id", "data"}
        for item in raw["events"]:
            if not isinstance(item, dict) or set(item) != expected_event_fields:
                raise ValueError("audit event fields do not match schema v1")
            events.append(OutcomeAuditEvent(
                item["sequence"], item["kind"], item["stage"], item["step_id"], item["data"],
            ))
        audit = cls(raw["task_id"], raw["arm"], raw["seed"], tuple(events), raw["schema_id"])
        if audit.canonical_json() != value:
            raise ValueError("audit JSON must use canonical encoding")
        return audit
def targeted_correction_reevaluation_receipts(
    audits: Sequence[EpisodeAudit],
    *,
    correction_id: str,
    memory_id: str,
    superseded_version: int,
    corrected_version: int,
) -> dict[str, Any]:
    """Emit content-free advisories for decisions that relied on the corrected version.

    Only an exact ``(memory_id, version)`` reference in a ``relied_on`` audit
    event qualifies. Merely exposed memories, related memories, or other
    versions do not trigger an advisory.
    """
    for label, value in (("correction_id", correction_id), ("memory_id", memory_id)):
        if not isinstance(value, str) or _FIELD.fullmatch(value) is None:
            raise ValueError(f"{label} must be a stable identifier")
    if (not isinstance(superseded_version, int) or isinstance(superseded_version, bool)
            or superseded_version < 0 or not isinstance(corrected_version, int)
            or isinstance(corrected_version, bool) or corrected_version <= superseded_version):
        raise ValueError("correction must advance the superseded memory version")
    if not isinstance(audits, Sequence) or isinstance(audits, (str, bytes)):
        raise ValueError("audits must be a bounded sequence of EpisodeAudit values")
    if len(audits) > 100_000:
        raise ValueError("audit sequence exceeds the correction advisory bound")
    seen_audits: set[tuple[str, str, int]] = set()
    receipts: list[dict[str, Any]] = []
    for audit in audits:
        if not isinstance(audit, EpisodeAudit):
            raise ValueError("audits must contain EpisodeAudit values")
        key = (audit.task_id, audit.arm, audit.seed)
        if key in seen_audits:
            raise ValueError("duplicate task/arm/seed audit in correction input")
        seen_audits.add(key)
        for event in audit.events:
            if event.kind is not OutcomeAuditKind.MEMORY_USE or event.step_id is None:
                continue
            data = _thaw_audit(event.data)
            if data.get("use") != "relied_on":
                continue
            matched = [
                [ref[0], ref[1]] for ref in data["evidence_versions"]
                if ref[0] == memory_id and ref[1] == superseded_version
            ]
            if not matched:
                continue
            receipt = {
                "correction_id": correction_id,
                "task_id": audit.task_id,
                "arm": audit.arm,
                "world_seed": audit.seed,
                "step_id": event.step_id,
                "status": "ADVISORY_REEVALUATION_REQUIRED",
                "trigger": "EXACT_RELIED_ON_VERSION_CORRECTED",
                "affected_evidence": matched,
            }
            receipt["receipt_id"] = hashlib.sha256(_audit_encode(
                receipt, limit=MAX_AUDIT_EVENT_BYTES,
            )).hexdigest()
            receipts.append(receipt)
    return {
        "schema_id": "memory-fabric.correction-reevaluation-advisories.v1",
        "correction_id": correction_id,
        "memory_id": memory_id,
        "superseded_version": superseded_version,
        "corrected_version": corrected_version,
        "status": "ADVISORIES_EMITTED" if receipts else "NO_AFFECTED_DECISIONS",
        "receipt_count": len(receipts),
        "receipts": receipts,
        "exposed_only_decisions_triggered": False,
        "claim_scope": "exact_audit_link_routing_only_no_automatic_action_or_causal_claim",
    }


def summarize_audit_memory_links(audit: EpisodeAudit) -> dict[str, Any]:
    """Report actor-recorded exposure and reliance separately, without causal inference."""
    if not isinstance(audit, EpisodeAudit):
        raise TypeError("audit must be an EpisodeAudit")
    links: dict[str, dict[str, set[tuple[str, int]]]] = {}
    unlinked_exposures: set[tuple[str, int]] = set()
    for event in audit.events:
        if event.kind is not OutcomeAuditKind.MEMORY_USE:
            continue
        data = _thaw_audit(event.data)
        use = data["use"]
        refs = {(ref[0], ref[1]) for ref in data["evidence_versions"]}
        if event.step_id is None:
            if use == "exposed":
                unlinked_exposures.update(refs)
            continue
        step_links = links.setdefault(
            event.step_id, {"exposed": set(), "relied_on": set()},
        )
        step_links[use].update(refs)
    steps = []
    for step_id in sorted(links):
        exposed = sorted(links[step_id]["exposed"])
        relied_on = sorted(links[step_id]["relied_on"])
        steps.append({
            "step_id": step_id,
            "exposed_evidence_versions": [[memory_id, version]
                                           for memory_id, version in exposed],
            "relied_on_evidence_versions": [[memory_id, version]
                                            for memory_id, version in relied_on],
            "use_status": "RELIED_ON_RECORDED" if relied_on else (
                "EXPOSED_ONLY" if exposed else "NO_RECORDED_MEMORY_LINK"
            ),
            "causal_effect_established": False,
        })
    return {
        "schema_id": "memory-fabric.audit-memory-links.v1",
        "task_id": audit.task_id,
        "arm": audit.arm,
        "world_seed": audit.seed,
        "steps": steps,
        "unlinked_exposures": [[memory_id, version]
                                for memory_id, version in sorted(unlinked_exposures)],
        "causal_effect_established": False,
        "claim_scope": "recorded_seen_and_relied_on_links_only_no_causal_attribution",
    }


class ReplayFidelityLabel(StrEnum):
    EXACT = "EXACT"
    DIVERGED = "DIVERGED"
    UNVERIFIABLE = "UNVERIFIABLE"


class PolicyFlipLabel(StrEnum):
    FLIPPED = "FLIPPED"
    UNCHANGED = "UNCHANGED"
    UNDECIDABLE = "UNDECIDABLE"


class OutcomeBenefitLabel(StrEnum):
    IMPROVED = "IMPROVED"
    REGRESSED = "REGRESSED"
    NO_CHANGE = "NO_CHANGE"
    UNDECIDABLE = "UNDECIDABLE"


def label_counterfactual_evidence(
    *,
    replay_fidelity: ReplayFidelityLabel,
    baseline_decision_sha256: str | None,
    alternative_decision_sha256: str | None,
    baseline_terminal_outcome: bool | None,
    alternative_terminal_outcome: bool | None,
) -> dict[str, Any]:
    """Keep replay fidelity, policy changes, observed outcomes, and causality distinct.

    Terminal outcomes must come from the evaluator for the declared paired arms.
    This function labels their comparison and never turns replay behavior into a
    claim about physical root cause.
    """
    if not isinstance(replay_fidelity, ReplayFidelityLabel):
        raise ValueError("replay_fidelity must use ReplayFidelityLabel")
    decision_digests = (baseline_decision_sha256, alternative_decision_sha256)
    if any(value is not None and (
            not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None
    ) for value in decision_digests):
        raise ValueError("decision digests must be SHA-256 hex or absent")
    for label, outcome in (("baseline", baseline_terminal_outcome),
                           ("alternative", alternative_terminal_outcome)):
        if outcome is not None and not isinstance(outcome, bool):
            raise ValueError(f"{label} terminal outcome must be boolean or absent")

    baseline_digest, alternative_digest = decision_digests
    if baseline_digest is None or alternative_digest is None:
        policy_flip = PolicyFlipLabel.UNDECIDABLE
    elif baseline_digest == alternative_digest:
        policy_flip = PolicyFlipLabel.UNCHANGED
    else:
        policy_flip = PolicyFlipLabel.FLIPPED

    if baseline_terminal_outcome is None or alternative_terminal_outcome is None:
        benefit = OutcomeBenefitLabel.UNDECIDABLE
    elif baseline_terminal_outcome == alternative_terminal_outcome:
        benefit = OutcomeBenefitLabel.NO_CHANGE
    elif alternative_terminal_outcome:
        benefit = OutcomeBenefitLabel.IMPROVED
    else:
        benefit = OutcomeBenefitLabel.REGRESSED

    return {
        "schema_id": "memory-fabric.counterfactual-evidence-labels.v1",
        "replay_fidelity": replay_fidelity.value,
        "policy_flip": policy_flip.value,
        "outcome_benefit": benefit.value,
        "outcome_basis": "paired_terminal_grader_outcomes",
        "real_world_causality": "NOT_ESTABLISHED",
        "causal_effect_established": False,
        "physical_root_cause_established": False,
        "claim_scope": "separate_replay_fidelity_decision_change_and_observed_outcome_labels",
    }

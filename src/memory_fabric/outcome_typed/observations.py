"""Bounded, canonical runtime contracts for outcome-driven agents."""

from __future__ import annotations

__stability__ = "experimental"

import hashlib
import hmac
import json
import re
import secrets
from dataclasses import dataclass, field as dataclass_field
from enum import StrEnum
from types import MappingProxyType
from typing import Any, ClassVar, Mapping

SCHEMA_ID = "memory-fabric.agent-outcomes.v3"
ORACLE_SCHEMA_ID = "memory-fabric.oracle-task.v1"
MAX_JSON_BYTES = 64_000
_FORBIDDEN = frozenset({
    "truth", "expected_action", "evidence_usable", "evidence_conflicted",
    "reward", "correct_answer", "answer_key", "eligibility_oracle", "oracle",
    "oracle_task", "oracle_sha256", "hidden_answer", "ground_truth", "eligibility",
    "eligible", "eligible_effects", "grading", "grader_output",
    "oracle_payload", "evaluator_capability", "oracle_capability",
    "terminal_grade", "grading_result",
    "hidden", "answerable", "expected_state", "expected_terminal_state",
    "correct_action", "evaluation_result", "evaluator_output",
})
_FORBIDDEN_NORMALIZED = frozenset(re.sub(r"[^a-z0-9]", "", item)
                                   for item in _FORBIDDEN)
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_INTENTS = frozenset({"retrieve", "inspect", "request_refresh", "ask", "propose", "abstain"})
_CAPABILITY_ISSUER = object()


class FailureCode(StrEnum):
    """Supported terminal task failure classes for raw outcome records."""

    RETRIEVAL_MISS = "retrieval_miss"
    MISSING_OBSERVATION = "missing_observation"
    UNSUPPORTED_CLAIM = "unsupported_claim"
    FALSE_POLICY_DENIAL = "false_policy_denial"
    AUTHORIZATION_DENIAL = "authorization_denial"
    PLANNING_ERROR = "planning_error"
    TOOL_ERROR = "tool_error"
    COORDINATION_ERROR = "coordination_error"
    STALE_DATA = "stale_data"
    ABSTENTION_COST = "abstention_cost"


FAILURE_CODES = frozenset(code.value for code in FailureCode)


def _canonical(value: Any) -> bytes:
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"),
                              ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (RecursionError, TypeError, ValueError) as exc:
        raise ValueError("contract values must be finite JSON data") from exc
    if len(encoded) > MAX_JSON_BYTES:
        raise ValueError("contract payload exceeds the size limit")
    return encoded


def _load_contract_json(value: str, *, label: str) -> Any:
    """Decode bounded JSON while rejecting ambiguous duplicate keys and constants."""
    if not isinstance(value, str):
        raise ValueError(f"{label} must be JSON text")
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError(f"{label} must be valid UTF-8 JSON") from exc
    if len(encoded) > MAX_JSON_BYTES:
        raise ValueError("contract payload exceeds the size limit")

    def object_from_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, item in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON field {key!r} is ambiguous")
            result[key] = item
        return result

    def reject_constant(constant: str) -> None:
        raise ValueError(f"non-finite JSON constant {constant!r} is forbidden")

    try:
        return json.loads(value, object_pairs_hook=object_from_pairs,
                          parse_constant=reject_constant)
    except (json.JSONDecodeError, RecursionError) as exc:
        raise ValueError(f"{label} is malformed JSON") from exc


def _no_oracle_fields(value: Any, path: str = "$", *,
                      _active: set[int] | None = None, _depth: int = 0) -> None:
    if _depth > 64:
        raise ValueError(f"actor payload nesting exceeds the limit at {path}")
    if callable(value) or getattr(type(value), "__evaluator_only__", False):
        raise ValueError(f"evaluator handle or callable is forbidden at {path}")
    active = set() if _active is None else _active
    if isinstance(value, Mapping):
        identity = id(value)
        if identity in active:
            raise ValueError(f"cyclic actor payload at {path}")
        active.add(identity)
        for key, child in value.items():
            if not isinstance(key, str):
                raise ValueError(f"non-string field at {path}")
            folded = key.casefold()
            normalized = re.sub(r"[^a-z0-9]", "", folded)
            if (folded in _FORBIDDEN or normalized in _FORBIDDEN_NORMALIZED
                    or normalized.startswith(("oracle", "evaluator", "grader", "hidden"))):
                raise ValueError(f"evaluator-only field is forbidden at {path}.{key}")
            _no_oracle_fields(child, f"{path}.{key}", _active=active, _depth=_depth + 1)
        active.remove(identity)
    elif isinstance(value, (list, tuple)):
        identity = id(value)
        if identity in active:
            raise ValueError(f"cyclic actor payload at {path}")
        active.add(identity)
        for index, child in enumerate(value):
            _no_oracle_fields(child, f"{path}[{index}]", _active=active, _depth=_depth + 1)
        active.remove(identity)


def _freeze_json(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze_json(child) for key, child in value.items()})
    if isinstance(value, list):
        return tuple(_freeze_json(child) for child in value)
    return value


def _thaw_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw_json(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_thaw_json(child) for child in value]
    return value


def _valid_id(value: str, field: str) -> None:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError(f"{field} must be a 1–128 character stable identifier")


@dataclass(frozen=True, init=False, repr=False)
class EvaluatorCapability:
    """Opaque task-bound bearer capability for in-process evaluator APIs.

    This protects ordinary API flows and serialization boundaries. Python
    reflection is not a security sandbox; callers must never pass this object
    to an actor or an untrusted callback.
    """

    __evaluator_only__: ClassVar[bool] = True
    _task_id: str
    _nonce: bytes
    _seal_sha256: str

    def __init__(self, issuer: object, task_id: str, nonce: bytes,
                 seal_sha256: str) -> None:
        if issuer is not _CAPABILITY_ISSUER:
            raise PermissionError("evaluator capabilities are issued by the host boundary")
        _valid_id(task_id, "task_id")
        if not isinstance(nonce, bytes) or len(nonce) != 32:
            raise ValueError("evaluator capability nonce must contain 32 bytes")
        if not isinstance(seal_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", seal_sha256):
            raise ValueError("evaluator capability must bind a SHA-256 seal")
        object.__setattr__(self, "_task_id", task_id)
        object.__setattr__(self, "_nonce", nonce)
        object.__setattr__(self, "_seal_sha256", seal_sha256)

    @classmethod
    def _issue(cls, task_id: str, nonce: bytes, seal_sha256: str) -> "EvaluatorCapability":
        return cls(_CAPABILITY_ISSUER, task_id, nonce, seal_sha256)

    def _authorizes(self, task_id: str, *, nonce: bytes | None = None,
                    seal_sha256: str | None = None) -> bool:
        if self._task_id != task_id:
            return False
        if nonce is not None and not hmac.compare_digest(self._nonce, nonce):
            return False
        if seal_sha256 is not None and not hmac.compare_digest(self._seal_sha256, seal_sha256):
            return False
        return True

    def __repr__(self) -> str:
        return "EvaluatorCapability(<opaque>)"

    def __reduce__(self) -> tuple[Any, ...]:
        raise TypeError("evaluator capabilities cannot be serialized")


@dataclass(frozen=True)
class AgentObservation:
    """Only legal, visible task data; never includes evaluator labels."""

    task_id: str
    instruction: str
    visible_events: tuple[Mapping[str, Any], ...]
    permitted_tools: tuple[str, ...]
    budget: Mapping[str, int]
    schema_id: str = SCHEMA_ID

    def __post_init__(self) -> None:
        _valid_id(self.task_id, "task_id")
        if self.schema_id != SCHEMA_ID:
            raise ValueError("unsupported observation schema")
        if not isinstance(self.instruction, str) or len(self.instruction.encode("utf-8")) > 16_000:
            raise ValueError("instruction must be text of at most 16000 bytes")
        if not isinstance(self.visible_events, (tuple, list)) or not all(
                isinstance(item, Mapping) for item in self.visible_events):
            raise ValueError("visible_events must contain JSON objects")
        if not isinstance(self.permitted_tools, (tuple, list)) or not all(
                isinstance(tool, str) and _ID.fullmatch(tool) for tool in self.permitted_tools):
            raise ValueError("permitted_tools must contain stable identifiers")
        if not isinstance(self.budget, Mapping) or any(
            not isinstance(k, str) or not isinstance(v, int) or isinstance(v, bool) or v < 0
            for k, v in self.budget.items()
        ):
            raise ValueError("budget values must be non-negative integers")
        untrusted = {
            "schema_id": self.schema_id,
            "task_id": self.task_id,
            "instruction": self.instruction,
            "visible_events": self.visible_events,
            "permitted_tools": self.permitted_tools,
            "budget": self.budget,
        }
        _no_oracle_fields(untrusted)
        frozen = _freeze_json(json.loads(_canonical(_thaw_json(untrusted))))
        object.__setattr__(self, "visible_events", tuple(frozen["visible_events"]))
        object.__setattr__(self, "permitted_tools", tuple(self.permitted_tools))
        object.__setattr__(self, "budget", frozen["budget"])

    def to_dict(self) -> dict[str, Any]:
        value = {"schema_id": self.schema_id, "task_id": self.task_id,
                 "instruction": self.instruction,
                 "visible_events": _thaw_json(self.visible_events),
                 "permitted_tools": list(self.permitted_tools),
                 "budget": _thaw_json(self.budget)}
        _no_oracle_fields(value)
        return value

    def canonical_json(self) -> str:
        return _canonical(self.to_dict()).decode("utf-8")

    def request_digest(self) -> str:
        """Hash the request without persisting its potentially sensitive content."""
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()

    @classmethod
    def from_json(cls, value: str) -> "AgentObservation":
        raw = _load_contract_json(value, label="observation")
        expected = {"schema_id", "task_id", "instruction", "visible_events", "permitted_tools", "budget"}
        if not isinstance(raw, dict) or set(raw) != expected:
            raise ValueError("observation fields do not match schema v3")
        return cls(task_id=raw["task_id"], instruction=raw["instruction"],
                   visible_events=tuple(raw["visible_events"]),
                   permitted_tools=tuple(raw["permitted_tools"]), budget=raw["budget"],
                   schema_id=raw["schema_id"])


@dataclass(frozen=True, repr=False)
class OracleTask:
    """Evaluator-side truth envelope, stored separately from agent observations.

    The canonical payload remains private and is committed by a SHA-256 seal.
    This is an integrity boundary, not an in-process secrecy mechanism; callers
    must keep the object out of actor arguments and actor-visible event data.
    """

    __evaluator_only__: ClassVar[bool] = True

    task_id: str
    _sealed_payload: bytes = dataclass_field(repr=False)
    seal_sha256: str
    schema_id: str = ORACLE_SCHEMA_ID
    _capability_nonce: bytes = dataclass_field(default=b"", repr=False, compare=False)

    def __post_init__(self) -> None:
        _valid_id(self.task_id, "task_id")
        if self.schema_id != ORACLE_SCHEMA_ID:
            raise ValueError("unsupported oracle task schema")
        if not isinstance(self._sealed_payload, bytes) or len(self._sealed_payload) > MAX_JSON_BYTES:
            raise ValueError("sealed oracle payload must be bounded canonical bytes")
        if not isinstance(self.seal_sha256, str) or not re.fullmatch(
            r"[0-9a-f]{64}", self.seal_sha256
        ):
            raise ValueError("oracle seal must be a SHA-256 hex digest")
        if self._capability_nonce and (
                not isinstance(self._capability_nonce, bytes)
                or len(self._capability_nonce) != 32):
            raise ValueError("oracle evaluator capability nonce must contain 32 bytes")
        if not self._verify_seal():
            raise ValueError("oracle payload does not match its seal")

    @classmethod
    def seal(cls, task_id: str, oracle_payload: Mapping[str, Any]) -> "OracleTask":
        """Seal a world-specific oracle payload with required hidden labels."""
        encoded = cls._encode_payload(task_id, oracle_payload)
        return cls(task_id, encoded, hashlib.sha256(encoded).hexdigest())

    @classmethod
    def seal_for_evaluator(
        cls, task_id: str, oracle_payload: Mapping[str, Any],
    ) -> tuple["OracleTask", EvaluatorCapability]:
        """Seal hidden truth and issue the host evaluator's task-bound capability."""
        encoded = cls._encode_payload(task_id, oracle_payload)
        digest = hashlib.sha256(encoded).hexdigest()
        nonce = secrets.token_bytes(32)
        oracle = cls(task_id, encoded, digest, _capability_nonce=nonce)
        return oracle, EvaluatorCapability._issue(task_id, nonce, digest)

    @classmethod
    def _encode_payload(cls, task_id: str, oracle_payload: Mapping[str, Any]) -> bytes:
        if not isinstance(oracle_payload, Mapping):
            raise ValueError("oracle_payload must be a JSON object")
        payload = dict(oracle_payload)
        missing = {"truth", "eligibility", "reward"} - payload.keys()
        if missing:
            raise ValueError(f"oracle payload is missing required fields: {sorted(missing)}")
        return _canonical({"schema_id": ORACLE_SCHEMA_ID, "task_id": task_id,
                           "oracle_payload": payload})

    def verify_seal(self, capability: EvaluatorCapability) -> bool:
        """Check the seal using the task-bound evaluator capability."""
        self._require_capability(capability)
        return self._verify_seal()

    def _verify_seal(self) -> bool:
        if hashlib.sha256(self._sealed_payload).hexdigest() != self.seal_sha256:
            return False
        try:
            envelope = json.loads(self._sealed_payload)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return False
        if (not isinstance(envelope, dict)
                or set(envelope) != {"schema_id", "task_id", "oracle_payload"}
                or envelope["schema_id"] != self.schema_id
                or envelope["task_id"] != self.task_id
                or not isinstance(envelope["oracle_payload"], dict)
                or not {"truth", "eligibility", "reward"} <= envelope["oracle_payload"].keys()):
            return False
        try:
            return _canonical(envelope) == self._sealed_payload
        except ValueError:
            return False

    def open_payload(self, capability: EvaluatorCapability) -> Mapping[str, Any]:
        """Return evaluator truth only to the capability for this sealed task."""
        self._require_capability(capability)
        if not self._verify_seal():
            raise ValueError("oracle payload does not match its seal")
        envelope = json.loads(self._sealed_payload)
        return _freeze_json(envelope["oracle_payload"])

    def _require_capability(self, capability: EvaluatorCapability) -> None:
        if (not isinstance(capability, EvaluatorCapability)
                or not capability._authorizes(
                    self.task_id, nonce=self._capability_nonce,
                    seal_sha256=self.seal_sha256)
                or not self._capability_nonce):
            raise PermissionError("evaluator capability required for this oracle task")

    def __repr__(self) -> str:
        return (f"OracleTask(task_id={self.task_id!r}, schema_id={self.schema_id!r}, "
                f"seal_sha256={self.seal_sha256!r})")


@dataclass(frozen=True)
class AgentStep:
    task_id: str
    actor_id: str
    step_id: str
    intent: str
    arguments: Mapping[str, Any]
    evidence_versions: tuple[tuple[str, int], ...] = ()
    schema_id: str = SCHEMA_ID

    def __post_init__(self) -> None:
        for field, value in (("task_id", self.task_id), ("actor_id", self.actor_id),
                             ("step_id", self.step_id)):
            _valid_id(value, field)
        if (self.schema_id != SCHEMA_ID or not isinstance(self.intent, str)
                or self.intent not in _INTENTS):
            raise ValueError("unsupported step schema or intent")
        if not isinstance(self.arguments, Mapping):
            raise ValueError("arguments must be a JSON object")
        _no_oracle_fields(self.arguments)
        if not isinstance(self.evidence_versions, (tuple, list)):
            raise ValueError("evidence_versions must be a bounded tuple of pairs")
        for item in self.evidence_versions:
            if (not isinstance(item, tuple) or len(item) != 2 or not isinstance(item[0], str)
                    or not isinstance(item[1], int) or item[1] < 0):
                raise ValueError("evidence_versions must be (memory_id, non-negative version) pairs")
        object.__setattr__(self, "evidence_versions", tuple(self.evidence_versions))
        arguments = _freeze_json(json.loads(_canonical(_thaw_json(self.arguments))))
        object.__setattr__(self, "arguments", arguments)
        _canonical(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        value = {"schema_id": self.schema_id, "task_id": self.task_id, "actor_id": self.actor_id,
                 "step_id": self.step_id, "intent": self.intent,
                 "arguments": _thaw_json(self.arguments),
                 "evidence_versions": [list(pair) for pair in self.evidence_versions]}
        _no_oracle_fields(value)
        return value

    def canonical_json(self) -> str:
        """Return stable JSON for this actor request without hidden metadata."""
        return _canonical(self.to_dict()).decode("utf-8")

    def request_digest(self) -> str:
        """Hash the exact canonical step request for safe correlation in logs."""
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()

    @classmethod
    def from_json(cls, value: str) -> "AgentStep":
        raw = _load_contract_json(value, label="agent step")
        expected = {"schema_id", "task_id", "actor_id", "step_id", "intent",
                    "arguments", "evidence_versions"}
        if not isinstance(raw, dict) or set(raw) != expected:
            raise ValueError("agent step fields do not match schema v3")
        versions = raw["evidence_versions"]
        if not isinstance(versions, list):
            raise ValueError("agent step evidence_versions must be a JSON array")
        pairs: list[tuple[str, int]] = []
        for item in versions:
            if not isinstance(item, list) or len(item) != 2:
                raise ValueError("agent step evidence_versions must contain pairs")
            pairs.append((item[0], item[1]))
        return cls(task_id=raw["task_id"], actor_id=raw["actor_id"],
                   step_id=raw["step_id"], intent=raw["intent"],
                   arguments=raw["arguments"], evidence_versions=tuple(pairs),
                   schema_id=raw["schema_id"])


@dataclass(frozen=True)
class EpisodeOutcome:
    __evaluator_only__: ClassVar[bool] = True

    task_id: str
    arm: str
    seed: int
    completion: bool
    safety_violations: int
    stale_effects: int
    rejected_effects: int
    eligible_recoveries: int
    successful_recoveries: int
    model_calls: int
    model_tokens: int
    wall_ms: float
    outcome_oracle_digest: str
    schema_id: str = SCHEMA_ID
    attempted_unsafe_effects: int = 0
    executed_unsafe_effects: int = 0
    terminal_failure_codes: tuple[str, ...] = ()
    agent_id: str = "system"

    def __post_init__(self) -> None:
        _valid_id(self.task_id, "task_id")
        _valid_id(self.arm, "arm")
        _valid_id(self.agent_id, "agent_id")
        if self.schema_id != SCHEMA_ID or self.seed < 0:
            raise ValueError("unsupported outcome schema or seed")
        for name in ("safety_violations", "stale_effects", "rejected_effects", "eligible_recoveries",
                     "successful_recoveries", "model_calls", "model_tokens",
                     "attempted_unsafe_effects", "executed_unsafe_effects"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if self.successful_recoveries > self.eligible_recoveries:
            raise ValueError("successful recoveries cannot exceed eligible recoveries")
        if self.executed_unsafe_effects > self.attempted_unsafe_effects:
            raise ValueError("executed unsafe effects cannot exceed attempted unsafe effects")
        if not isinstance(self.completion, bool) or self.wall_ms < 0:
            raise ValueError("completion must be boolean and wall_ms non-negative")
        if not re.fullmatch(r"[0-9a-f]{64}", self.outcome_oracle_digest):
            raise ValueError("outcome oracle digest must be a SHA-256 hex digest")
        if (not isinstance(self.terminal_failure_codes, tuple)
                or any(not isinstance(code, str) for code in self.terminal_failure_codes)):
            raise ValueError("terminal_failure_codes must be a tuple of strings")
        if len(set(self.terminal_failure_codes)) != len(self.terminal_failure_codes):
            raise ValueError("terminal failure codes must be unique")
        unsupported = set(self.terminal_failure_codes) - FAILURE_CODES
        if unsupported:
            raise ValueError(f"unsupported terminal failure codes: {sorted(unsupported)}")
        if self.completion and self.terminal_failure_codes:
            raise ValueError("completed episodes cannot have terminal failure codes")
        if not self.completion and not self.terminal_failure_codes:
            raise ValueError("failed episodes require at least one terminal failure code")

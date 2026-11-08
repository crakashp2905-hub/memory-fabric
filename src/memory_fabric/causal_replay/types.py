"""Versioned, immutable CDM data contracts and canonical hashing."""

from __future__ import annotations

__stability__ = "experimental"

import hashlib
import json
import math
import re
from dataclasses import MISSING, asdict, dataclass
from enum import Enum
from typing import Any, Mapping

SCHEMA_MAJOR = 1
SCHEMA_MINOR = 0
SCHEMA = f"memory-fabric-cdm-v{SCHEMA_MAJOR}"
_SCHEMA_RE = re.compile(r"^memory-fabric-cdm-v(0|[1-9][0-9]*)(?:\.(0|[1-9][0-9]*))?$")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,255}$")


def schema_version(value: str) -> tuple[int, int]:
    """Parse the CDM major/minor namespace; vN is the vN.0 spelling."""
    if not isinstance(value, str):
        raise CDMError("schema version must be text")
    match = _SCHEMA_RE.fullmatch(value)
    if match is None:
        raise CDMError("schema version is malformed")
    return int(match.group(1)), int(match.group(2) or 0)


def schema_is_compatible(value: str) -> bool:
    """Accept current-major schemas no newer than this implementation."""
    try:
        major, minor = schema_version(value)
    except CDMError:
        return False
    return major == SCHEMA_MAJOR and minor <= SCHEMA_MINOR


class CDMError(ValueError):
    """Base class for stable, fail-closed CDM errors."""

    code = "INVALID_INPUT"


class Unauthorized(CDMError):
    code = "UNAUTHORIZED"


class Erased(CDMError):
    code = "ERASED"


class NonReplayable(CDMError):
    code = "NON_REPLAYABLE"


class BudgetExceeded(CDMError):
    code = "BUDGET_EXCEEDED"


class InvalidIntervention(CDMError):
    code = "INTERVENTION_INVALID"


class TraceIncomplete(CDMError):
    code = "TRACE_INCOMPLETE"


class SimulatorForbidden(CDMError):
    code = "SIMULATOR_FORBIDDEN"


class ReplayStatus(str, Enum):
    EXACT = "EXACT"
    APPROXIMATE = "APPROXIMATE"
    NON_REPLAYABLE = "NON_REPLAYABLE"


@dataclass(frozen=True)
class RNGSnapshot:
    """Full Python MT19937 continuation state, including its internal position."""

    algorithm: str
    state_version: int
    internal_state: tuple[int, ...]
    gaussian_next: float | None
    position: int

    def to_stdlib_state(self) -> tuple[int, tuple[int, ...], float | None]:
        return self.state_version, self.internal_state, self.gaussian_next

    def __post_init__(self) -> None:
        if (self.algorithm != "python.random.MT19937" or type(self.state_version) is not int
                or not self.internal_state or any(type(item) is not int
                or not 0 <= item <= 0xFFFFFFFF for item in self.internal_state)
                or type(self.position) is not int or self.position != self.internal_state[-1]
                or not 0 <= self.position <= 624
                or (self.gaussian_next is not None
                    and not isinstance(self.gaussian_next, (int, float)))):
            raise CDMError("RNG snapshot is malformed or incomplete")
        if self.gaussian_next is not None and not math.isfinite(self.gaussian_next):
            raise CDMError("RNG Gaussian cache must be finite")


def canonical_json(value: Any) -> str:
    """Canonical JSON: sorted keys, compact UTF-8 representation, finite numbers only."""
    def validate(node: Any, depth: int = 0) -> None:
        if depth > 64:
            raise CDMError("JSON nesting exceeds 64 levels")
        if isinstance(node, float) and not math.isfinite(node):
            raise CDMError("non-finite numbers are not allowed")
        if isinstance(node, str):
            try:
                node.encode("utf-8", "strict")
            except UnicodeEncodeError as exc:
                raise CDMError("invalid Unicode string") from exc
        elif isinstance(node, Mapping):
            for key, item in node.items():
                if not isinstance(key, str):
                    raise CDMError("JSON object keys must be strings")
                validate(key, depth + 1)
                validate(item, depth + 1)
        elif isinstance(node, (tuple, list)):
            for item in node:
                validate(item, depth + 1)
        elif node is None or isinstance(node, (bool, int)):
            return
        elif not isinstance(node, float):
            raise CDMError(f"unsupported JSON value type: {type(node).__name__}")
    validate(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False)


def digest_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _identifier(value: str, label: str) -> None:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise CDMError(f"{label} is malformed")


@dataclass(frozen=True)
class EventReference:
    event_id: str
    sequence: int
    tenant_id: str
    digest: str

    def __post_init__(self) -> None:
        _identifier(self.event_id, "event_id")
        _identifier(self.tenant_id, "tenant_id")
        if type(self.sequence) is not int or self.sequence < 0:
            raise CDMError("sequence must be a non-negative integer")
        if not re.fullmatch(r"[0-9a-f]{64}", self.digest):
            raise CDMError("digest must be a lowercase SHA-256 hex string")


@dataclass(frozen=True)
class BeliefReference:
    belief_id: str
    version: int
    tenant_id: str
    digest: str

    def __post_init__(self) -> None:
        _identifier(self.belief_id, "belief_id")
        _identifier(self.tenant_id, "tenant_id")
        if type(self.version) is not int or self.version < 1:
            raise CDMError("version must be a positive integer")
        if not re.fullmatch(r"[0-9a-f]{64}", self.digest):
            raise CDMError("digest must be a lowercase SHA-256 hex string")


@dataclass(frozen=True)
class DecisionRecord:
    sequence: int
    tenant_id: str
    agent_id: str
    options: tuple[str, ...]
    selected: str | None
    evidence: tuple[BeliefReference, ...]
    policy_id: str
    policy_digest: str
    schema: str = SCHEMA
    constraints: tuple[str, ...] = ()
    source_event_id: str | None = None
    rng_applicability: str = "not_applicable_deterministic"
    rng_state: RNGSnapshot | None = None
    tool_observations: tuple[ToolObservation, ...] = ()

    def __post_init__(self) -> None:
        if type(self.sequence) is not int or self.sequence < 0:
            raise CDMError("decision sequence must be non-negative")
        _identifier(self.tenant_id, "tenant_id")
        _identifier(self.agent_id, "agent_id")
        _identifier(self.policy_id, "policy_id")
        if (self.schema != SCHEMA or not self.options
                or any(not isinstance(item, str) or not item for item in self.options)
                or len(set(self.options)) != len(self.options)
                or type(self.constraints) is not tuple
                or any(not isinstance(item, str) or not item for item in self.constraints)
                or len(set(self.constraints)) != len(self.constraints)):
            raise CDMError("decision schema/options are invalid")
        if self.selected is not None and self.selected not in self.options:
            raise CDMError("selected option is not declared")
        if self.source_event_id is not None:
            _identifier(self.source_event_id, "source_event_id")
        if (self.rng_applicability not in {"captured_full_state",
                "not_applicable_deterministic", "missing_state_non_replayable"}
                or (self.rng_applicability == "captured_full_state"
                    and type(self.rng_state) is not RNGSnapshot)
                or (self.rng_applicability != "captured_full_state" and self.rng_state is not None)
                or type(self.tool_observations) is not tuple
                or any(type(item) is not ToolObservation for item in self.tool_observations)):
            raise CDMError("RNG or tool determinism metadata is invalid")
        if not re.fullmatch(r"[0-9a-f]{64}", self.policy_digest):
            raise CDMError("policy_digest must be SHA-256")


@dataclass(frozen=True)
class ReplayContext:
    known_at: int
    valid_at: int | None = None
    wall_clock_ms: int | None = None
    max_events: int = 10_000

    def __post_init__(self) -> None:
        for label, value in (("known_at", self.known_at), ("valid_at", self.valid_at),
                             ("wall_clock_ms", self.wall_clock_ms)):
            if value is not None and type(value) is not int:
                raise CDMError(f"{label} must be an integer")
        if self.known_at < 0 or (self.valid_at is not None and self.valid_at < 0):
            raise CDMError("sequence and valid time must be non-negative")
        if not 1 <= self.max_events <= 100_000:
            raise CDMError("max_events must be in [1, 100000]")


@dataclass(frozen=True)
class ToolObservation:
    actor_id: str
    tool_id: str
    schema_digest: str
    input_digest: str
    output_digest: str
    determinism: str

    def __post_init__(self) -> None:
        _identifier(self.actor_id, "actor_id")
        _identifier(self.tool_id, "tool_id")
        for label in ("schema_digest", "input_digest", "output_digest"):
            if not re.fullmatch(r"[0-9a-f]{64}", getattr(self, label)):
                raise CDMError(f"{label} must be SHA-256")
        if self.determinism not in {"exogenous", "simulated_endogenous", "opaque"}:
            raise CDMError("unknown determinism class")


@dataclass(frozen=True)
class CaptureResult:
    schema: str
    principal_id: str
    tenant_id: str
    known_at: int
    valid_at: int | None
    source_head: int
    evidence: tuple[BeliefReference, ...]
    complete: bool
    factual_digest: str
    archival_only: bool = True
    source_currently_admissible: bool = True
    historical_snapshot_only: bool = True
    decision: DecisionRecord | None = None

    def __post_init__(self) -> None:
        if (self.schema != SCHEMA or not self.archival_only
                or type(self.source_currently_admissible) is not bool
                or type(self.historical_snapshot_only) is not bool):
            raise CDMError("capture must be a v1 archival-only record")
        _identifier(self.principal_id, "principal_id")
        _identifier(self.tenant_id, "tenant_id")
        if self.decision is not None:
            if (type(self.decision) is not DecisionRecord
                    or self.decision.tenant_id != self.tenant_id
                    or self.decision.agent_id != self.principal_id
                    or self.decision.sequence > self.known_at
                    or not set(self.decision.evidence) <= set(self.evidence)):
                raise CDMError("captured decision does not match capture identity, time or evidence")
        if (type(self.known_at) is not int or type(self.source_head) is not int
                or self.known_at < 0 or self.source_head < self.known_at):
            raise CDMError("capture sequence bounds are invalid")
        if not re.fullmatch(r"[0-9a-f]{64}", self.factual_digest):
            raise CDMError("factual_digest must be SHA-256")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


RECORD_TYPES = (EventReference, BeliefReference, DecisionRecord, ReplayContext,
                ToolObservation, CaptureResult, RNGSnapshot)


def serialize_record(value: Any) -> str:
    """Serialize only registered v1 records through canonical JSON."""
    if type(value) not in RECORD_TYPES:
        raise CDMError("unregistered record type")
    return canonical_json(asdict(value))


def parse_record(record_type: type, value: str | dict[str, Any]) -> Any:
    """Strictly parse a registered record; reject unknown or missing fields."""
    if record_type not in RECORD_TYPES:
        raise CDMError("unregistered record type")
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (ValueError, TypeError) as exc:
            raise CDMError("invalid record JSON") from exc
    else:
        parsed = value
    if type(parsed) is not dict:
        raise CDMError("record JSON must be an object")
    fields = record_type.__dataclass_fields__
    required = {name for name, field in fields.items()
                if field.default is MISSING and field.default_factory is MISSING}
    if set(parsed) - set(fields) or required - set(parsed):
        raise CDMError("record fields are missing or unknown")
    body = dict(parsed)
    if "schema" in body:
        if not isinstance(body["schema"], str) or not schema_is_compatible(body["schema"]):
            raise CDMError("record schema major/minor is unsupported")
        body["schema"] = SCHEMA
    if record_type in (DecisionRecord, CaptureResult):
        key = "evidence"
        if key in body:
            if type(body[key]) is not list:
                raise CDMError("evidence must be a JSON array")
            body[key] = tuple(parse_record(BeliefReference, item) for item in body[key])
    if record_type is CaptureResult and body.get("decision") is not None:
        body["decision"] = parse_record(DecisionRecord, body["decision"])
    if record_type is DecisionRecord:
        if body.get("rng_state") is not None:
            body["rng_state"] = parse_record(RNGSnapshot, body["rng_state"])
        if "tool_observations" in body:
            if type(body["tool_observations"]) is not list:
                raise CDMError("tool_observations must be a JSON array")
            body["tool_observations"] = tuple(
                parse_record(ToolObservation, item) for item in body["tool_observations"])
    if record_type is DecisionRecord and "options" in body:
        if type(body["options"]) is not list:
            raise CDMError("options must be a JSON array")
        body["options"] = tuple(body["options"])
    if record_type is DecisionRecord and "constraints" in body:
        if type(body["constraints"]) is not list:
            raise CDMError("constraints must be a JSON array")
        body["constraints"] = tuple(body["constraints"])
    if record_type is RNGSnapshot and "internal_state" in body:
        if type(body["internal_state"]) is not list:
            raise CDMError("RNG internal_state must be a JSON array")
        body["internal_state"] = tuple(body["internal_state"])
    try:
        return record_type(**body)
    except (TypeError, KeyError) as exc:
        raise CDMError("record fields do not match schema") from exc

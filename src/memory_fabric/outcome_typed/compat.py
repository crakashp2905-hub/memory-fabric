"""Versioned translations from the two legacy outcome packages to the canonical one (W02-03).

ADR 0004 makes :mod:`memory_fabric.outcome_typed` the canonical outcome runtime.
``memory_fabric.agent_outcomes`` and ``memory_fabric.outcome_protocol`` stay
importable for historical research but write schema v1; this module converts
their records to canonical schema v3 and back where that is lossless.

Every field that both schemas can represent is preserved. A field one side
cannot represent is never invented or silently dropped: the translation raises
:class:`IncompatibleRecord` with the reason, and the caller decides (for
example by supplying the unsafe-effect counts a v1 outcome never recorded).
Identity and version semantics (task, actor, step and evidence version) are
validated by the canonical constructors, so a mismatched identity cannot be
reinterpreted on the way through (W02-05).
"""

from __future__ import annotations

__stability__ = "experimental"

from dataclasses import fields
from typing import Any, Mapping, Sequence

from .observations import SCHEMA_ID as CANONICAL_SCHEMA_ID
from .observations import AgentObservation, AgentStep, EpisodeOutcome
from .recovery import RecoveryStatus

LEGACY_SCHEMA_ID = "memory-fabric.agent-outcomes.v1"
LEGACY_PACKAGES = ("memory_fabric.agent_outcomes", "memory_fabric.outcome_protocol")
SUNSET = "2027-03-31"


class IncompatibleRecord(ValueError):
    """A record that cannot be translated without inventing or dropping a field."""

    def __init__(self, kind: str, reason: str) -> None:
        super().__init__(f"{kind}: {reason}")
        self.kind = kind
        self.reason = reason


def _as_dict(value: Any, kind: str) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return dict(to_dict())
    if hasattr(value, "__dataclass_fields__"):
        return {item.name: getattr(value, item.name) for item in fields(value)}
    raise IncompatibleRecord(kind, f"unsupported source type {type(value).__name__}")


def _legacy_module(value: Any) -> str:
    module = type(value).__module__
    for package in LEGACY_PACKAGES:
        if module.startswith(package + "."):
            return package
    return module


def observation_from_legacy(value: Any) -> AgentObservation:
    data = _as_dict(value, "observation")
    if data.get("schema_id") != LEGACY_SCHEMA_ID:
        raise IncompatibleRecord("observation", f"expected {LEGACY_SCHEMA_ID}")
    try:
        return AgentObservation(task_id=data["task_id"], instruction=data["instruction"],
                                visible_events=tuple(data["visible_events"]),
                                permitted_tools=tuple(data["permitted_tools"]),
                                budget=dict(data["budget"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise IncompatibleRecord("observation", f"rejected by the canonical schema: {exc}") from exc


def step_from_legacy(value: Any) -> AgentStep:
    data = _as_dict(value, "step")
    if data.get("schema_id") != LEGACY_SCHEMA_ID:
        raise IncompatibleRecord("step", f"expected {LEGACY_SCHEMA_ID}")
    try:
        versions = tuple(tuple(pair) for pair in data.get("evidence_versions", ()))
        return AgentStep(task_id=data["task_id"], actor_id=data["actor_id"],
                         step_id=data["step_id"], intent=data["intent"],
                         arguments=dict(data["arguments"]), evidence_versions=versions)
    except (KeyError, TypeError, ValueError) as exc:
        raise IncompatibleRecord("step", f"rejected by the canonical schema: {exc}") from exc


def observation_to_legacy(value: AgentObservation, cls: type) -> Any:
    """Canonical observation to a legacy class; the payload fields are identical."""
    data = value.to_dict()
    try:
        return cls(task_id=data["task_id"], instruction=data["instruction"],
                   visible_events=tuple(data["visible_events"]),
                   permitted_tools=tuple(data["permitted_tools"]), budget=dict(data["budget"]))
    except (TypeError, ValueError) as exc:
        raise IncompatibleRecord("observation", f"rejected by the legacy schema: {exc}") from exc


def step_to_legacy(value: AgentStep, cls: type) -> Any:
    data = value.to_dict()
    try:
        return cls(task_id=data["task_id"], actor_id=data["actor_id"], step_id=data["step_id"],
                   intent=data["intent"], arguments=dict(data["arguments"]),
                   evidence_versions=tuple(tuple(pair) for pair in data["evidence_versions"]))
    except (TypeError, ValueError) as exc:
        raise IncompatibleRecord("step", f"rejected by the legacy schema: {exc}") from exc


_V1_OUTCOME_FIELDS = ("task_id", "arm", "seed", "completion", "safety_violations",
                      "stale_effects", "rejected_effects", "eligible_recoveries",
                      "successful_recoveries", "model_calls", "model_tokens", "wall_ms",
                      "outcome_oracle_digest")


def outcome_from_legacy(value: Any, *, attempted_unsafe_effects: int | None = None,
                        executed_unsafe_effects: int | None = None,
                        terminal_failure_codes: Sequence[str] | None = None,
                        agent_id: str = "system") -> EpisodeOutcome:
    """A v1 outcome needs the facts v1 never recorded; they are never defaulted."""
    data = _as_dict(value, "outcome")
    if data.get("schema_id") != LEGACY_SCHEMA_ID:
        raise IncompatibleRecord("outcome", f"expected {LEGACY_SCHEMA_ID}")
    if attempted_unsafe_effects is None or executed_unsafe_effects is None:
        raise IncompatibleRecord("outcome", "schema v1 does not record attempted and executed "
                                            "unsafe effects; supply them explicitly")
    if not data.get("completion") and not terminal_failure_codes:
        raise IncompatibleRecord("outcome", "an incomplete v1 outcome has no terminal failure "
                                            "codes; supply them explicitly")
    try:
        return EpisodeOutcome(**{name: data[name] for name in _V1_OUTCOME_FIELDS},
                              attempted_unsafe_effects=attempted_unsafe_effects,
                              executed_unsafe_effects=executed_unsafe_effects,
                              terminal_failure_codes=tuple(terminal_failure_codes or ()),
                              agent_id=agent_id)
    except (KeyError, TypeError, ValueError) as exc:
        raise IncompatibleRecord("outcome", f"rejected by the canonical schema: {exc}") from exc


def outcome_to_legacy(value: EpisodeOutcome, cls: type) -> Any:
    """Refuse when v3-only facts would be lost; otherwise return the v1 record."""
    lost = {"attempted_unsafe_effects": value.attempted_unsafe_effects,
            "executed_unsafe_effects": value.executed_unsafe_effects,
            "terminal_failure_codes": value.terminal_failure_codes}
    if any(lost.values()) or value.agent_id != "system":
        raise IncompatibleRecord("outcome", "schema v1 cannot carry unsafe-effect counts, "
                                            "failure codes or agent identity")
    return cls(**{name: getattr(value, name) for name in _V1_OUTCOME_FIELDS})


def recovery_status_from_legacy(value: Any) -> RecoveryStatus:
    name = getattr(value, "name", value)
    if not isinstance(name, str) or name not in RecoveryStatus.__members__:
        raise IncompatibleRecord("recovery_status",
                                 f"{name!r} has no canonical equivalent (e.g. DISABLED)")
    return RecoveryStatus[name]


def recovery_status_to_legacy(value: RecoveryStatus, enum: Any) -> Any:
    if value.name not in enum.__members__:
        raise IncompatibleRecord("recovery_status",
                                 f"{value.name} has no equivalent in {enum.__module__}")
    return enum[value.name]


def describe() -> dict[str, Any]:
    return {"canonical_package": "memory_fabric.outcome_typed",
            "canonical_schema_id": CANONICAL_SCHEMA_ID, "legacy_schema_id": LEGACY_SCHEMA_ID,
            "legacy_packages": list(LEGACY_PACKAGES), "sunset": SUNSET}

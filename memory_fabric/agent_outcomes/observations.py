"""Bounded, canonical runtime contracts for outcome-driven agents."""

from __future__ import annotations

__stability__ = "experimental"

import hashlib
import json
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping

SCHEMA_ID = "memory-fabric.agent-outcomes.v3"
MAX_JSON_BYTES = 64_000
_FORBIDDEN = frozenset({
    "truth", "expected_action", "evidence_usable", "evidence_conflicted",
    "reward", "correct_answer", "answer_key", "eligibility_oracle",
})
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_INTENTS = frozenset({"retrieve", "inspect", "request_refresh", "ask", "propose", "abstain"})


class FailureCode(StrEnum):
    """Supported terminal task failure classes for raw outcome records."""

    RETRIEVAL_MISS = "retrieval_miss"
    MISSING_OBSERVATION = "missing_observation"
    UNSUPPORTED_CLAIM = "unsupported_claim"
    FALSE_POLICY_DENIAL = "false_policy_denial"
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
    except (TypeError, ValueError) as exc:
        raise ValueError("contract values must be finite JSON data") from exc
    if len(encoded) > MAX_JSON_BYTES:
        raise ValueError("contract payload exceeds the size limit")
    return encoded


def _no_oracle_fields(value: Any, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                raise ValueError(f"non-string field at {path}")
            if key.casefold() in _FORBIDDEN:
                raise ValueError(f"evaluator-only field is forbidden at {path}.{key}")
            _no_oracle_fields(child, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _no_oracle_fields(child, f"{path}[{index}]")


def _valid_id(value: str, field: str) -> None:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError(f"{field} must be a 1–128 character stable identifier")


@dataclass(frozen=True)
class AgentObservation:
    """Only legal, visible task data; never includes evaluator labels."""

    task_id: str
    instruction: str
    visible_events: tuple[dict[str, Any], ...]
    permitted_tools: tuple[str, ...]
    budget: dict[str, int]
    schema_id: str = SCHEMA_ID

    def __post_init__(self) -> None:
        _valid_id(self.task_id, "task_id")
        if self.schema_id != SCHEMA_ID:
            raise ValueError("unsupported observation schema")
        if not isinstance(self.instruction, str) or len(self.instruction.encode("utf-8")) > 16_000:
            raise ValueError("instruction must be text of at most 16000 bytes")
        if not all(isinstance(item, dict) for item in self.visible_events):
            raise ValueError("visible_events must contain JSON objects")
        if not all(isinstance(tool, str) and _ID.fullmatch(tool) for tool in self.permitted_tools):
            raise ValueError("permitted_tools must contain stable identifiers")
        if not isinstance(self.budget, dict) or any(
            not isinstance(k, str) or not isinstance(v, int) or isinstance(v, bool) or v < 0
            for k, v in self.budget.items()
        ):
            raise ValueError("budget values must be non-negative integers")
        _no_oracle_fields(self.to_dict())
        _canonical(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {"schema_id": self.schema_id, "task_id": self.task_id,
                "instruction": self.instruction, "visible_events": list(self.visible_events),
                "permitted_tools": list(self.permitted_tools), "budget": self.budget}

    def canonical_json(self) -> str:
        return _canonical(self.to_dict()).decode("utf-8")

    def request_digest(self) -> str:
        """Hash the request without persisting its potentially sensitive content."""
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()

    @classmethod
    def from_json(cls, value: str) -> "AgentObservation":
        if len(value.encode("utf-8")) > MAX_JSON_BYTES:
            raise ValueError("contract payload exceeds the size limit")
        raw = json.loads(value)
        expected = {"schema_id", "task_id", "instruction", "visible_events", "permitted_tools", "budget"}
        if not isinstance(raw, dict) or set(raw) != expected:
            raise ValueError("observation fields do not match schema v1")
        return cls(task_id=raw["task_id"], instruction=raw["instruction"],
                   visible_events=tuple(raw["visible_events"]),
                   permitted_tools=tuple(raw["permitted_tools"]), budget=raw["budget"],
                   schema_id=raw["schema_id"])


@dataclass(frozen=True)
class AgentStep:
    task_id: str
    actor_id: str
    step_id: str
    intent: str
    arguments: dict[str, Any]
    evidence_versions: tuple[tuple[str, int], ...] = ()
    schema_id: str = SCHEMA_ID

    def __post_init__(self) -> None:
        for field, value in (("task_id", self.task_id), ("actor_id", self.actor_id),
                             ("step_id", self.step_id)):
            _valid_id(value, field)
        if self.schema_id != SCHEMA_ID or self.intent not in _INTENTS:
            raise ValueError("unsupported step schema or intent")
        if not isinstance(self.arguments, dict):
            raise ValueError("arguments must be a JSON object")
        _no_oracle_fields(self.arguments)
        for item in self.evidence_versions:
            if (not isinstance(item, tuple) or len(item) != 2 or not isinstance(item[0], str)
                    or not isinstance(item[1], int) or item[1] < 0):
                raise ValueError("evidence_versions must be (memory_id, non-negative version) pairs")
        _canonical(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {"schema_id": self.schema_id, "task_id": self.task_id, "actor_id": self.actor_id,
                "step_id": self.step_id, "intent": self.intent, "arguments": self.arguments,
                "evidence_versions": [list(pair) for pair in self.evidence_versions]}


@dataclass(frozen=True)
class EpisodeOutcome:
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

    def __post_init__(self) -> None:
        _valid_id(self.task_id, "task_id")
        _valid_id(self.arm, "arm")
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

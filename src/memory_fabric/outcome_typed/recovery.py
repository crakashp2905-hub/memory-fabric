"""Bounded recovery helpers that leave authorization with the host's ActionGate."""

from __future__ import annotations

__stability__ = "experimental"

import hashlib
import json
import math
import time
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Callable, Mapping

from ..actions_typed import ALREADY_EXECUTED, EXECUTED, ActionExecution, ActionGate, ActionRequest, Grant
from ..certificates import EvidenceCertificate
from .privacy import scrub_public_json

MAX_RECOVERY_STEPS = 1_024
MAX_RECOVERY_ATTEMPTS = 128
MAX_RECOVERY_EVENT_BYTES = 64_000
MAX_RECOVERY_DEADLINE_S = 3_600.0
MAX_RECOVERY_AUDIT_BYTES = 1_000_000
RECOVERY_AUDIT_SCHEMA_ID = "memory-fabric.recovery-audit.v3"
RECOVERY_CHECKPOINT_SCHEMA_ID = "memory-fabric.recovery-checkpoint.v1"
_RECOVERY_FAILURE_REASONS = frozenset({
    "deadline_exceeded", "step_budget_exhausted", "invalid_event",
    "event_size_exceeded", "recovery_action_pending",
    "recovery_attempt_budget_exhausted", "invalid_progress_token",
    "recovery_action_mismatch", "no_monotonic_progress",
})
_RECOVERY_INTERNAL_EVENTS = frozenset({
    "recovery_requested", "recovery_progress", "recovery_rejected",
    "failure_guidance", "propose", "action_gate",
})


class RecoveryStatus(StrEnum):
    READY = "READY"
    BLOCKED = "BLOCKED"
    RECOVERED = "RECOVERED"
    ESCALATED = "ESCALATED"
    ABSTAINED = "ABSTAINED"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


class RecoveryAction(StrEnum):
    """Recovery catalog contains information gathering and planning only."""

    REFRESH = "refresh"
    RE_RETRIEVE = "re_retrieve"
    INSPECT_PROVENANCE = "inspect_provenance"
    REQUEST_OBSERVATION = "request_observation"
    ASK_CLARIFICATION = "ask_clarification"
    REPLAN = "replan"


class RecoveryCause(StrEnum):
    """Closed causes for selecting a safe fallback, escalation, or abstention."""

    MISSING = "missing"
    WITHHELD = "withheld"
    IRRELEVANT = "irrelevant"
    STALE = "stale"
    CONTESTED = "contested"
    UNAUTHORIZED = "unauthorized"
    ERASED = "erased"
    DUPLICATE = "duplicate"
    INSUFFICIENT = "insufficient"
    NO_INDEPENDENT_SOURCE = "no_independent_source"
    RECOVERY_BUDGET_EXHAUSTED = "recovery_budget_exhausted"
    NO_MONOTONIC_PROGRESS = "no_monotonic_progress"
    UNKNOWN = "unknown"


class RecoveryFailureClass(StrEnum):
    RETRIEVAL = "retrieval"
    AUTHORIZATION = "authorization"
    EVIDENCE_VALIDITY = "evidence_validity"
    RECOVERY_CONTROL = "recovery_control"
    UNKNOWN = "unknown"


class RecoveryResolution(StrEnum):
    FALLBACK = "fallback"
    ESCALATE = "escalate"
    ABSTAIN = "abstain"


class RecoveryNextAction(StrEnum):
    """Typed guidance; only read-only catalog values can be recovery steps."""

    RE_RETRIEVE = "re_retrieve"
    REFRESH = "refresh"
    INSPECT_PROVENANCE = "inspect_provenance"
    REQUEST_OBSERVATION = "request_observation"
    ASK_CLARIFICATION = "ask_clarification"
    REQUEST_OWNER_REVIEW = "request_owner_review"
    REQUEST_OPERATOR_REVIEW = "request_operator_review"
    ABSTAIN = "abstain"


@dataclass(frozen=True)
class RecoveryGuidance:
    """Content-free, closed guidance that cannot grant or perform an effect."""

    SCHEMA_ID = "memory-fabric.recovery-guidance.v1"

    cause: RecoveryCause
    resolution: RecoveryResolution
    next_action: RecoveryNextAction
    requires_human: bool

    def __post_init__(self) -> None:
        if (not isinstance(self.cause, RecoveryCause)
                or not isinstance(self.resolution, RecoveryResolution)
                or not isinstance(self.next_action, RecoveryNextAction)):
            raise ValueError("recovery guidance fields must use the closed enums")
        if not isinstance(self.requires_human, bool):
            raise ValueError("requires_human must be a boolean")
        if self.resolution is RecoveryResolution.FALLBACK:
            if self.next_action.value not in {action.value for action in RecoveryAction}:
                raise ValueError("fallback guidance must name a read-only recovery action")
            if self.requires_human:
                raise ValueError("read-only fallback guidance cannot require escalation")
        elif self.resolution is RecoveryResolution.ESCALATE:
            if self.next_action not in {
                RecoveryNextAction.REQUEST_OWNER_REVIEW,
                RecoveryNextAction.REQUEST_OPERATOR_REVIEW,
            } or not self.requires_human:
                raise ValueError("escalation must request human owner or operator review")
        elif (self.next_action is not RecoveryNextAction.ABSTAIN
              or self.requires_human):
            raise ValueError("abstention guidance must stop without an automatic override")

    def to_json(self) -> dict[str, str | bool]:
        return {
            "schema_id": self.SCHEMA_ID,
            "cause": self.cause.value,
            "resolution": self.resolution.value,
            "next_action": self.next_action.value,
            "requires_human": self.requires_human,
        }


_RECOVERY_GUIDANCE: Mapping[RecoveryCause, RecoveryGuidance] = MappingProxyType({
    RecoveryCause.MISSING: RecoveryGuidance(
        RecoveryCause.MISSING, RecoveryResolution.FALLBACK,
        RecoveryNextAction.RE_RETRIEVE, False),
    RecoveryCause.WITHHELD: RecoveryGuidance(
        RecoveryCause.WITHHELD, RecoveryResolution.ESCALATE,
        RecoveryNextAction.REQUEST_OWNER_REVIEW, True),
    RecoveryCause.IRRELEVANT: RecoveryGuidance(
        RecoveryCause.IRRELEVANT, RecoveryResolution.FALLBACK,
        RecoveryNextAction.RE_RETRIEVE, False),
    RecoveryCause.STALE: RecoveryGuidance(
        RecoveryCause.STALE, RecoveryResolution.FALLBACK,
        RecoveryNextAction.REFRESH, False),
    RecoveryCause.CONTESTED: RecoveryGuidance(
        RecoveryCause.CONTESTED, RecoveryResolution.FALLBACK,
        RecoveryNextAction.INSPECT_PROVENANCE, False),
    RecoveryCause.UNAUTHORIZED: RecoveryGuidance(
        RecoveryCause.UNAUTHORIZED, RecoveryResolution.ESCALATE,
        RecoveryNextAction.REQUEST_OWNER_REVIEW, True),
    RecoveryCause.ERASED: RecoveryGuidance(
        RecoveryCause.ERASED, RecoveryResolution.ESCALATE,
        RecoveryNextAction.REQUEST_OWNER_REVIEW, True),
    RecoveryCause.DUPLICATE: RecoveryGuidance(
        RecoveryCause.DUPLICATE, RecoveryResolution.FALLBACK,
        RecoveryNextAction.RE_RETRIEVE, False),
    RecoveryCause.INSUFFICIENT: RecoveryGuidance(
        RecoveryCause.INSUFFICIENT, RecoveryResolution.FALLBACK,
        RecoveryNextAction.REQUEST_OBSERVATION, False),
    RecoveryCause.NO_INDEPENDENT_SOURCE: RecoveryGuidance(
        RecoveryCause.NO_INDEPENDENT_SOURCE, RecoveryResolution.ESCALATE,
        RecoveryNextAction.REQUEST_OWNER_REVIEW, True),
    RecoveryCause.RECOVERY_BUDGET_EXHAUSTED: RecoveryGuidance(
        RecoveryCause.RECOVERY_BUDGET_EXHAUSTED, RecoveryResolution.ESCALATE,
        RecoveryNextAction.REQUEST_OPERATOR_REVIEW, True),
    RecoveryCause.NO_MONOTONIC_PROGRESS: RecoveryGuidance(
        RecoveryCause.NO_MONOTONIC_PROGRESS, RecoveryResolution.ESCALATE,
        RecoveryNextAction.REQUEST_OPERATOR_REVIEW, True),
    RecoveryCause.UNKNOWN: RecoveryGuidance(
        RecoveryCause.UNKNOWN, RecoveryResolution.ABSTAIN,
        RecoveryNextAction.ABSTAIN, False),
})

_RECOVERY_FAILURE_CLASSES: Mapping[RecoveryCause, RecoveryFailureClass] = MappingProxyType({
    RecoveryCause.MISSING: RecoveryFailureClass.RETRIEVAL,
    RecoveryCause.IRRELEVANT: RecoveryFailureClass.RETRIEVAL,
    RecoveryCause.DUPLICATE: RecoveryFailureClass.RETRIEVAL,
    RecoveryCause.INSUFFICIENT: RecoveryFailureClass.RETRIEVAL,
    RecoveryCause.NO_INDEPENDENT_SOURCE: RecoveryFailureClass.RETRIEVAL,
    RecoveryCause.WITHHELD: RecoveryFailureClass.AUTHORIZATION,
    RecoveryCause.UNAUTHORIZED: RecoveryFailureClass.AUTHORIZATION,
    RecoveryCause.STALE: RecoveryFailureClass.EVIDENCE_VALIDITY,
    RecoveryCause.CONTESTED: RecoveryFailureClass.EVIDENCE_VALIDITY,
    RecoveryCause.ERASED: RecoveryFailureClass.EVIDENCE_VALIDITY,
    RecoveryCause.RECOVERY_BUDGET_EXHAUSTED: RecoveryFailureClass.RECOVERY_CONTROL,
    RecoveryCause.NO_MONOTONIC_PROGRESS: RecoveryFailureClass.RECOVERY_CONTROL,
    RecoveryCause.UNKNOWN: RecoveryFailureClass.UNKNOWN,
})

_TERMINAL_RECOVERY_STATUSES = frozenset({
    RecoveryStatus.ESCALATED,
    RecoveryStatus.ABSTAINED,
    RecoveryStatus.COMPLETE,
    RecoveryStatus.FAILED,
})


_PERMITTED_READ_ONLY_ACTIONS = frozenset({
    RecoveryAction.REFRESH,
    RecoveryAction.RE_RETRIEVE,
    RecoveryAction.INSPECT_PROVENANCE,
    RecoveryAction.REQUEST_OBSERVATION,
    RecoveryAction.ASK_CLARIFICATION,
    RecoveryAction.REPLAN,
})


@dataclass(frozen=True)
class RecoveryActionSpec:
    action: RecoveryAction
    read_only: bool = True

    def __post_init__(self) -> None:
        if (not isinstance(self.action, RecoveryAction)
                or self.action not in _PERMITTED_READ_ONLY_ACTIONS):
            raise ValueError("recovery action is outside the read-only catalog")
        if self.read_only is not True:
            raise ValueError("recovery catalog actions must remain read-only")


RECOVERY_ACTIONS: Mapping[RecoveryAction, RecoveryActionSpec] = MappingProxyType({
    action: RecoveryActionSpec(action) for action in RecoveryAction
})


@dataclass(frozen=True)
class RecoveryLimits:
    max_steps: int = 8
    max_recoveries: int = 2
    max_event_bytes: int = 16_000
    deadline_s: float = 30.0

    def __post_init__(self) -> None:
        for field_name, value, maximum in (
            ("max_steps", self.max_steps, MAX_RECOVERY_STEPS),
            ("max_recoveries", self.max_recoveries, MAX_RECOVERY_ATTEMPTS),
            ("max_event_bytes", self.max_event_bytes, MAX_RECOVERY_EVENT_BYTES),
        ):
            if (not isinstance(value, int) or isinstance(value, bool)
                    or not 0 <= value <= maximum):
                raise ValueError(f"{field_name} must be between 0 and {maximum}")
        if (not isinstance(self.deadline_s, (int, float))
                or isinstance(self.deadline_s, bool)
                or not math.isfinite(self.deadline_s)
                or not 0 <= self.deadline_s <= MAX_RECOVERY_DEADLINE_S):
            raise ValueError(
                f"deadline_s must be finite and between 0 and {MAX_RECOVERY_DEADLINE_S}")


@dataclass
class RecoveryEpisode:
    """Tracks observable recovery progress; holds no world truth or grading labels."""

    task_id: str
    limits: RecoveryLimits = field(default_factory=RecoveryLimits)
    status: RecoveryStatus = RecoveryStatus.READY
    steps: int = 0
    recoveries: int = 0
    trace: list[dict[str, Any]] = field(default_factory=list)
    _started_at: float = field(init=False, repr=False)
    _seen_progress_digests: set[str] = field(default_factory=set, init=False, repr=False)
    _pending_action: RecoveryAction | None = field(default=None, init=False, repr=False)
    _before_token_digest: str | None = field(default=None, init=False, repr=False)
    _failure_reason: str | None = field(default=None, init=False, repr=False)
    _guidance: RecoveryGuidance | None = field(default=None, init=False, repr=False)
    _failure_counts: dict[RecoveryFailureClass, int] = field(
        default_factory=lambda: {kind: 0 for kind in RecoveryFailureClass},
        init=False, repr=False,
    )
    _action_counts: dict[RecoveryAction, int] = field(
        default_factory=lambda: {action: 0 for action in RecoveryAction},
        init=False, repr=False,
    )
    _requeries_avoided: int = field(default=0, init=False, repr=False)

    def __post_init__(self) -> None:
        self._started_at = time.monotonic()

    @property
    def failure_reason(self) -> str | None:
        return self._failure_reason

    def _fail(self, reason: str) -> None:
        self.status = RecoveryStatus.FAILED
        self._failure_reason = reason

    def _append_event(self, item: dict[str, Any]) -> bool:
        if time.monotonic() - self._started_at > self.limits.deadline_s:
            self._fail("deadline_exceeded")
            return False
        if self.steps >= self.limits.max_steps:
            self._fail("step_budget_exhausted")
            return False
        try:
            encoded = json.dumps(scrub_public_json(item), sort_keys=True, separators=(",", ":"),
                                 ensure_ascii=False, allow_nan=False).encode("utf-8")
        except (RecursionError, TypeError, ValueError):
            self._fail("invalid_event")
            return False
        if len(encoded) > self.limits.max_event_bytes:
            self._fail("event_size_exceeded")
            return False
        self.steps += 1
        self.trace.append(json.loads(encoded))
        return True

    def audit_record(self) -> dict[str, Any]:
        """Return a bounded audit snapshot with configured and consumed budgets."""
        value = {
            "schema_id": RECOVERY_AUDIT_SCHEMA_ID,
            "task_id": self.task_id,
            "status": self.status.value,
            "failure_reason": self._failure_reason,
            "guidance": self._guidance.to_json() if self._guidance else None,
            "budget": {
                "max_steps": self.limits.max_steps,
                "max_recoveries": self.limits.max_recoveries,
                "max_event_bytes": self.limits.max_event_bytes,
                "deadline_s": self.limits.deadline_s,
            },
            "used": {"steps": self.steps, "recoveries": self.recoveries},
            "telemetry": {
                "failure_classes": {
                    kind.value: self._failure_counts[kind]
                    for kind in RecoveryFailureClass
                },
                "recovery_actions": {
                    action.value: self._action_counts[action]
                    for action in RecoveryAction
                },
                "requeries_avoided": self._requeries_avoided,
            },
            "trace": self.trace,
        }
        try:
            encoded = json.dumps(value, sort_keys=True, separators=(",", ":"),
                                 ensure_ascii=False, allow_nan=False).encode("utf-8")
        except (RecursionError, TypeError, ValueError) as exc:
            raise ValueError("recovery audit is not finite JSON") from exc
        if len(encoded) > MAX_RECOVERY_AUDIT_BYTES:
            raise ValueError("recovery audit exceeds the size limit")
        return scrub_public_json(json.loads(encoded))

    def canonical_audit_json(self) -> str:
        """Serialize the audit deterministically, including the configured budget."""
        return json.dumps(self.audit_record(), sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False)

    def checkpoint_record(self) -> dict[str, Any]:
        """Return a bounded restart checkpoint; persist it before risky transitions.

        This checkpoint restores recovery bookkeeping only. Protected effects
        remain reconciled by the durable idempotency ledger in ``ActionGate``.
        """
        elapsed_s = max(0.0, time.monotonic() - self._started_at)
        value = {
            "schema_id": RECOVERY_CHECKPOINT_SCHEMA_ID,
            "audit": self.audit_record(),
            "elapsed_s": min(elapsed_s, float(self.limits.deadline_s)),
            "pending_action": (self._pending_action.value
                               if self._pending_action is not None else None),
            "before_token_digest": self._before_token_digest,
            "seen_progress_digests": sorted(self._seen_progress_digests),
            "requeries_avoided": self._requeries_avoided,
        }
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False, allow_nan=False).encode("utf-8")
        if len(encoded) > MAX_RECOVERY_AUDIT_BYTES:
            raise ValueError("recovery checkpoint exceeds the size limit")
        return scrub_public_json(json.loads(encoded))

    def canonical_checkpoint_json(self) -> str:
        """Serialize a restart checkpoint deterministically."""
        return json.dumps(self.checkpoint_record(), sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False)

    @classmethod
    def from_checkpoint(
        cls,
        checkpoint: str | Mapping[str, Any],
        *,
        downtime_s: float,
    ) -> RecoveryEpisode:
        """Restore bounded recovery state from a checkpoint after a process restart.

        The caller supplies elapsed downtime so the episode deadline continues
        across the process boundary. If it exceeds the remaining budget, the
        restored episode fails closed as ``deadline_exceeded``.
        """
        if (not isinstance(downtime_s, (int, float)) or isinstance(downtime_s, bool)
                or not math.isfinite(downtime_s) or downtime_s < 0):
            raise ValueError("downtime_s must be a finite non-negative number")
        if isinstance(checkpoint, str):
            if len(checkpoint.encode("utf-8")) > MAX_RECOVERY_AUDIT_BYTES:
                raise ValueError("recovery checkpoint exceeds the size limit")

            def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
                result: dict[str, Any] = {}
                for key, item in pairs:
                    if key in result:
                        raise ValueError("recovery checkpoint has duplicate JSON fields")
                    result[key] = item
                return result

            def reject_constant(value: str) -> None:
                raise ValueError(f"recovery checkpoint contains {value}")

            try:
                value = json.loads(checkpoint, object_pairs_hook=unique_object,
                                   parse_constant=reject_constant)
            except (json.JSONDecodeError, RecursionError) as exc:
                raise ValueError("recovery checkpoint is malformed JSON") from exc
        elif isinstance(checkpoint, Mapping):
            value = dict(checkpoint)
        else:
            raise ValueError("recovery checkpoint must be JSON text or a mapping")
        try:
            encoded = json.dumps(value, sort_keys=True, separators=(",", ":"),
                                 ensure_ascii=False, allow_nan=False).encode("utf-8")
        except (RecursionError, TypeError, ValueError) as exc:
            raise ValueError("recovery checkpoint must be finite JSON") from exc
        if len(encoded) > MAX_RECOVERY_AUDIT_BYTES:
            raise ValueError("recovery checkpoint exceeds the size limit")
        if not isinstance(value, dict) or value.get("schema_id") != RECOVERY_CHECKPOINT_SCHEMA_ID:
            raise ValueError("unsupported recovery checkpoint schema")
        if set(value) != {
                "schema_id", "audit", "elapsed_s", "pending_action",
                "before_token_digest", "seen_progress_digests", "requeries_avoided"}:
            raise ValueError("recovery checkpoint fields do not match the schema")
        cleaned = scrub_public_json(value)
        if cleaned != value:
            raise ValueError("recovery checkpoint contains private or invalid content")
        audit = value["audit"]
        if (not isinstance(audit, dict)
                or set(audit) != {"schema_id", "task_id", "status", "failure_reason",
                                  "guidance", "budget", "used", "telemetry", "trace"}
                or audit.get("schema_id") != RECOVERY_AUDIT_SCHEMA_ID):
            raise ValueError("recovery checkpoint has an invalid audit record")
        elapsed_s = value["elapsed_s"]
        if (not isinstance(elapsed_s, (int, float)) or isinstance(elapsed_s, bool)
                or not math.isfinite(elapsed_s) or elapsed_s < 0):
            raise ValueError("recovery checkpoint elapsed time is invalid")
        limits_value = audit.get("budget")
        if not isinstance(limits_value, dict) or set(limits_value) != {
                "max_steps", "max_recoveries", "max_event_bytes", "deadline_s"}:
            raise ValueError("recovery checkpoint budget is invalid")
        try:
            limits = RecoveryLimits(**limits_value)
            status = RecoveryStatus(audit["status"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("recovery checkpoint status or budget is invalid") from exc
        if not isinstance(audit.get("task_id"), str) or not audit["task_id"]:
            raise ValueError("recovery checkpoint task ID is invalid")
        used, trace, telemetry = audit.get("used"), audit.get("trace"), audit.get("telemetry")
        if (not isinstance(used, dict) or set(used) != {"steps", "recoveries"}
                or not isinstance(trace, list) or not isinstance(telemetry, dict)):
            raise ValueError("recovery checkpoint audit counters or trace are invalid")
        steps, recoveries = used.get("steps"), used.get("recoveries")
        if (not isinstance(steps, int) or isinstance(steps, bool)
                or steps != len(trace) or steps > limits.max_steps
                or not isinstance(recoveries, int) or isinstance(recoveries, bool)
                or recoveries < 0 or recoveries > limits.max_recoveries):
            raise ValueError("recovery checkpoint counters do not match its budget")
        for event in trace:
            if (not isinstance(event, dict) or not isinstance(event.get("kind"), str)
                    or not event["kind"]):
                raise ValueError("recovery checkpoint trace is malformed")
            try:
                event_bytes = json.dumps(
                    scrub_public_json(event), sort_keys=True, separators=(",", ":"),
                    ensure_ascii=False, allow_nan=False,
                ).encode("utf-8")
            except (RecursionError, TypeError, ValueError) as exc:
                raise ValueError("recovery checkpoint trace event is invalid") from exc
            if len(event_bytes) > limits.max_event_bytes:
                raise ValueError("recovery checkpoint trace event exceeds its limit")

        parsed_pending: RecoveryAction | None = None
        parsed_before: str | None = None
        seen_digests: set[str] = set()
        action_counts = {action: 0 for action in RecoveryAction}
        failure_counts = {failure: 0 for failure in RecoveryFailureClass}
        request_count = 0
        pending_proposal = False
        last_gate_outcome: str | None = None
        for event in trace:
            kind = event["kind"]
            if kind == "recovery_requested":
                if parsed_pending is not None:
                    raise ValueError("recovery checkpoint has overlapping pending actions")
                try:
                    parsed_pending = RecoveryAction(event["action"])
                except (KeyError, TypeError, ValueError) as exc:
                    raise ValueError("recovery checkpoint has an unknown action") from exc
                parsed_before = event.get("before_token_digest")
                if (not isinstance(parsed_before, str) or len(parsed_before) != 64
                        or any(char not in "0123456789abcdef" for char in parsed_before)):
                    raise ValueError("recovery checkpoint progress digest is invalid")
                seen_digests.add(parsed_before)
                action_counts[parsed_pending] += 1
                request_count += 1
            elif kind in {"recovery_progress", "recovery_rejected"}:
                if parsed_pending is None or event.get("action") != parsed_pending.value:
                    raise ValueError("recovery checkpoint resolves an unrequested action")
                if kind == "recovery_progress":
                    after_digest = event.get("after_token_digest")
                    if (not isinstance(after_digest, str) or len(after_digest) != 64
                            or any(char not in "0123456789abcdef" for char in after_digest)
                            or after_digest in seen_digests):
                        raise ValueError("recovery checkpoint progress is malformed or repeated")
                    seen_digests.add(after_digest)
                parsed_pending = None
                parsed_before = None
            elif kind == "failure_guidance":
                detail = event.get("detail")
                cause_value = detail.get("cause") if isinstance(detail, dict) else None
                if not isinstance(cause_value, str):
                    raise ValueError("recovery checkpoint guidance cause is invalid")
                try:
                    cause = RecoveryCause(cause_value)
                except (TypeError, ValueError) as exc:
                    raise ValueError("recovery checkpoint guidance cause is invalid") from exc
                failure_counts[_RECOVERY_FAILURE_CLASSES[cause]] += 1
            elif kind == "propose":
                if pending_proposal:
                    raise ValueError("recovery checkpoint has overlapping action proposals")
                detail = event.get("detail")
                if (not isinstance(detail, dict) or not isinstance(detail.get("tool"), str)
                        or not detail["tool"] or not isinstance(detail.get("key"), str)
                        or not detail["key"]):
                    raise ValueError("recovery checkpoint action proposal is invalid")
                pending_proposal = True
            elif kind == "action_gate":
                if not pending_proposal:
                    raise ValueError("recovery checkpoint has an unproposed ActionGate result")
                detail = event.get("detail")
                if (not isinstance(detail, dict) or not isinstance(detail.get("outcome"), str)
                        or not isinstance(detail.get("reason_codes"), list)
                        or any(not isinstance(code, str) for code in detail["reason_codes"])):
                    raise ValueError("recovery checkpoint ActionGate result is invalid")
                pending_proposal = False
                last_gate_outcome = detail["outcome"]
        if request_count != recoveries:
            raise ValueError("recovery checkpoint recovery count disagrees with its trace")
        if value["pending_action"] != (parsed_pending.value if parsed_pending else None):
            raise ValueError("recovery checkpoint pending action disagrees with its trace")
        if value["before_token_digest"] != parsed_before:
            raise ValueError("recovery checkpoint pending digest disagrees with its trace")
        supplied_seen = value["seen_progress_digests"]
        if (not isinstance(supplied_seen, list) or supplied_seen != sorted(seen_digests)):
            raise ValueError("recovery checkpoint progress history disagrees with its trace")
        if not isinstance(value["requeries_avoided"], int) or isinstance(
                value["requeries_avoided"], bool) or not 0 <= value["requeries_avoided"] <= MAX_RECOVERY_STEPS:
            raise ValueError("recovery checkpoint avoided-query count is invalid")
        expected_telemetry = {
            "failure_classes": {failure.value: failure_counts[failure]
                                for failure in RecoveryFailureClass},
            "recovery_actions": {action.value: action_counts[action]
                                 for action in RecoveryAction},
            "requeries_avoided": value["requeries_avoided"],
        }
        if telemetry != expected_telemetry:
            raise ValueError("recovery checkpoint telemetry disagrees with its trace")

        if pending_proposal:
            raise ValueError("recovery checkpoint ends with an unresolved action proposal")
        if status is RecoveryStatus.COMPLETE and last_gate_outcome not in {EXECUTED, ALREADY_EXECUTED}:
            raise ValueError("completed recovery checkpoint has no executed action receipt")

        reason = audit.get("failure_reason")
        if (reason is not None
                and (not isinstance(reason, str) or reason not in _RECOVERY_FAILURE_REASONS)):
            raise ValueError("recovery checkpoint failure reason is invalid")
        guidance_value = audit.get("guidance")
        guidance: RecoveryGuidance | None = None
        if guidance_value is not None:
            if (not isinstance(guidance_value, dict) or set(guidance_value) != {
                    "schema_id", "cause", "resolution", "next_action", "requires_human"}
                    or guidance_value.get("schema_id") != RecoveryGuidance.SCHEMA_ID):
                raise ValueError("recovery checkpoint guidance is invalid")
            try:
                guidance = RecoveryGuidance(
                    RecoveryCause(guidance_value["cause"]),
                    RecoveryResolution(guidance_value["resolution"]),
                    RecoveryNextAction(guidance_value["next_action"]),
                    guidance_value["requires_human"],
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError("recovery checkpoint guidance is invalid") from exc

        episode = cls(audit["task_id"], limits)
        episode.status = status
        episode.steps = steps
        episode.recoveries = recoveries
        episode.trace = json.loads(json.dumps(trace, sort_keys=True, separators=(",", ":")))
        episode._failure_reason = reason
        episode._guidance = guidance
        episode._failure_counts = failure_counts
        episode._action_counts = action_counts
        episode._requeries_avoided = value["requeries_avoided"]
        episode._pending_action = parsed_pending
        episode._before_token_digest = parsed_before
        episode._seen_progress_digests = seen_digests
        total_elapsed = float(elapsed_s) + float(downtime_s)
        if total_elapsed >= limits.deadline_s:
            episode._fail("deadline_exceeded")
            episode._pending_action = None
            episode._before_token_digest = None
        else:
            episode._started_at = time.monotonic() - total_elapsed
        return episode

    def record(self, kind: str, detail: Mapping[str, Any] | None = None) -> bool:
        """Append bounded, public trace metadata; return False when the step budget ends."""
        if not isinstance(kind, str) or not kind:
            raise ValueError("recovery event kind must be a non-empty string")
        if kind in _RECOVERY_INTERNAL_EVENTS:
            raise ValueError("recovery lifecycle events are emitted only by typed methods")
        if self.status in _TERMINAL_RECOVERY_STATUSES:
            return False
        if kind in {action.value for action in RecoveryAction}:
            raise ValueError("use request_recovery/resolve_recovery for typed recovery actions")
        if self._pending_action is not None:
            self._fail("recovery_action_pending")
            return False
        if not self._append_event({"kind": kind, "detail": dict(detail or {})}):
            return False
        if kind == "evidence_blocked":
            self.status = RecoveryStatus.BLOCKED
        elif kind == "abstain":
            self.status = RecoveryStatus.ABSTAINED
        return True

    def request_recovery(
        self,
        action: RecoveryAction,
        *,
        before_token: str,
        detail: Mapping[str, Any] | None = None,
    ) -> bool:
        """Begin a catalogued read-only step against a fingerprinted public state."""
        if not isinstance(action, RecoveryAction) or action not in RECOVERY_ACTIONS:
            raise ValueError("recovery action must be selected from the read-only catalog")
        if self.status in _TERMINAL_RECOVERY_STATUSES:
            if (action is RecoveryAction.RE_RETRIEVE and self._guidance is not None
                    and self._guidance.resolution in {
                        RecoveryResolution.ESCALATE, RecoveryResolution.ABSTAIN}):
                self._requeries_avoided = min(
                    self._requeries_avoided + 1, MAX_RECOVERY_STEPS)
            return False
        if self._pending_action is not None or self.recoveries >= self.limits.max_recoveries:
            self._fail("recovery_attempt_budget_exhausted"
                       if self.recoveries >= self.limits.max_recoveries
                       else "recovery_action_pending")
            return False
        if not self._valid_progress_token(before_token):
            self._fail("invalid_progress_token")
            return False
        token_digest = hashlib.sha256(before_token.encode("utf-8")).hexdigest()
        event = {"kind": "recovery_requested", "action": action.value,
                 "before_token_digest": token_digest, "detail": dict(detail or {})}
        if not self._append_event(event):
            return False
        self.recoveries += 1
        self._action_counts[action] += 1
        self._pending_action = action
        self._before_token_digest = token_digest
        self._seen_progress_digests.add(token_digest)
        return True

    def resolve_recovery(self, action: RecoveryAction, *, after_token: str) -> bool:
        """Accept only a changed, previously unseen public state fingerprint."""
        if action is not self._pending_action or self._before_token_digest is None:
            self._fail("recovery_action_mismatch")
            return False
        if not self._valid_progress_token(after_token):
            self._fail("invalid_progress_token")
            return False
        after_digest = hashlib.sha256(after_token.encode("utf-8")).hexdigest()
        if (after_digest == self._before_token_digest
                or after_digest in self._seen_progress_digests):
            self._append_event({"kind": "recovery_rejected", "action": action.value,
                                "reason": "no_monotonic_progress"})
            self._pending_action = None
            self._before_token_digest = None
            self._fail("no_monotonic_progress")
            return False
        if not self._append_event({"kind": "recovery_progress", "action": action.value,
                                   "after_token_digest": after_digest}):
            self._pending_action = None
            self._before_token_digest = None
            return False
        self._seen_progress_digests.add(after_digest)
        self._pending_action = None
        self._before_token_digest = None
        self.status = RecoveryStatus.RECOVERED
        return True

    def handle_failure(self, cause: RecoveryCause) -> RecoveryGuidance:
        """Record closed guidance and end in a safe fallback, escalation, or stop.

        Fallback guidance only selects a member of the read-only catalog; the
        caller must separately request that step. Escalation never changes a
        grant or performs an effect. A prior hard failure remains terminal.
        """
        if not isinstance(cause, RecoveryCause):
            raise ValueError("cause must be selected from the closed recovery taxonomy")
        if (self.status in {RecoveryStatus.COMPLETE, RecoveryStatus.ABSTAINED,
                            RecoveryStatus.ESCALATED}
                or self._pending_action is not None
                or (self._guidance is not None
                    and self._guidance.resolution is not RecoveryResolution.FALLBACK)):
            raise RuntimeError("episode already has a terminal result or pending recovery")
        guidance = _RECOVERY_GUIDANCE[cause]
        failure_class = _RECOVERY_FAILURE_CLASSES[cause]
        if not self._append_event({"kind": "failure_guidance", "detail": {
            "cause": guidance.cause.value,
            "resolution": guidance.resolution.value,
            "next_action": guidance.next_action.value,
        }}):
            return guidance
        self._failure_counts[failure_class] += 1
        self._guidance = guidance

        if guidance.resolution is RecoveryResolution.FALLBACK:
            if self.status is not RecoveryStatus.FAILED:
                self.status = RecoveryStatus.BLOCKED
        elif guidance.resolution is RecoveryResolution.ESCALATE:
            self.status = RecoveryStatus.ESCALATED
        else:
            self.status = RecoveryStatus.ABSTAINED
        return guidance

    @staticmethod
    def _valid_progress_token(value: Any) -> bool:
        if not isinstance(value, str) or not value:
            return False
        try:
            return len(value.encode("utf-8")) <= 512
        except UnicodeEncodeError:
            return False

    def execute(
        self,
        gate: ActionGate,
        tool: str,
        actor_id: str,
        certificate: EvidenceCertificate,
        run: Callable[[str], Any],
        *,
        key: str,
        request: ActionRequest | None = None,
        tenant_id: str | None = None,
        grant: Grant | str | None = None,
        session: Any = None,
        retry: bool = False,
    ) -> ActionExecution:
        """Reauthorize at effect time via the existing gate, then record only its verdict."""
        if self.status in _TERMINAL_RECOVERY_STATUSES:
            raise RuntimeError(f"episode is terminal: {self.status}")
        if not isinstance(retry, bool):
            raise ValueError("retry must be an explicit boolean")
        if not self._append_event({"kind": "propose", "detail": {"tool": tool, "key": key}}):
            raise RuntimeError("episode step budget exhausted")
        execution = gate.execute(tool, actor_id, run, certificate, key=key, request=request,
                                 tenant_id=tenant_id, grant=grant, session=session,
                                 retry=retry)
        recorded = self._append_event({"kind": "action_gate", "detail": {
            "outcome": execution.outcome,
            "reason_codes": list(execution.decision.reason_codes)
            if execution.decision else [],
        }})
        if execution.outcome in {EXECUTED, ALREADY_EXECUTED} and recorded:
            self.status = RecoveryStatus.COMPLETE
        elif recorded:
            self.status = RecoveryStatus.BLOCKED
        return execution


@dataclass(frozen=True)
class RecoveryFeatureFlag:
    """Explicit opt-in for integrations that want to create recovery episodes.

    The default is disabled. A disabled flag creates no state and does not
    wrap or alter legacy MemoryFabric, Session, or ActionGate calls.
    """

    enabled: bool = False
    limits: RecoveryLimits = field(default_factory=RecoveryLimits)

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, bool):
            raise ValueError("enabled must be a boolean")
        if not isinstance(self.limits, RecoveryLimits):
            raise ValueError("limits must be RecoveryLimits")

    def start_episode(self, task_id: str) -> RecoveryEpisode | None:
        """Create a bounded recovery episode only after explicit enablement."""
        if not self.enabled:
            return None
        return RecoveryEpisode(task_id, self.limits)

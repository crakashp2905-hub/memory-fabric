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

from ..actions import ActionExecution, ActionGate, ActionRequest, Grant
from ..certificates import EvidenceCertificate
from .privacy import scrub_public_json

MAX_RECOVERY_STEPS = 1_024
MAX_RECOVERY_ATTEMPTS = 128
MAX_RECOVERY_EVENT_BYTES = 64_000
MAX_RECOVERY_DEADLINE_S = 3_600.0
MAX_RECOVERY_AUDIT_BYTES = 1_000_000
RECOVERY_AUDIT_SCHEMA_ID = "memory-fabric.recovery-audit.v3"


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
    _seen_progress: set[str] = field(default_factory=set, init=False, repr=False)
    _pending_action: RecoveryAction | None = field(default=None, init=False, repr=False)
    _before_token: str | None = field(default=None, init=False, repr=False)
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

    def record(self, kind: str, detail: Mapping[str, Any] | None = None) -> bool:
        """Append bounded, public trace metadata; return False when the step budget ends."""
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
        self._before_token = before_token
        self._seen_progress.add(before_token)
        return True

    def resolve_recovery(self, action: RecoveryAction, *, after_token: str) -> bool:
        """Accept only a changed, previously unseen public state fingerprint."""
        if action is not self._pending_action or self._before_token is None:
            self._fail("recovery_action_mismatch")
            return False
        if not self._valid_progress_token(after_token):
            self._fail("invalid_progress_token")
            return False
        if after_token == self._before_token or after_token in self._seen_progress:
            self._append_event({"kind": "recovery_rejected", "action": action.value,
                                "reason": "no_monotonic_progress"})
            self._pending_action = None
            self._before_token = None
            self._fail("no_monotonic_progress")
            return False
        after_digest = hashlib.sha256(after_token.encode("utf-8")).hexdigest()
        if not self._append_event({"kind": "recovery_progress", "action": action.value,
                                   "after_token_digest": after_digest}):
            self._pending_action = None
            self._before_token = None
            return False
        self._seen_progress.add(after_token)
        self._pending_action = None
        self._before_token = None
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
        self._failure_counts[failure_class] += 1
        self._guidance = guidance
        if self.status is not RecoveryStatus.FAILED:
            if not self.record("failure_guidance", {
                "cause": guidance.cause.value,
                "resolution": guidance.resolution.value,
                "next_action": guidance.next_action.value,
            }):
                return guidance

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
    ) -> ActionExecution:
        """Reauthorize at effect time via the existing gate, then record only its verdict."""
        if self.status in _TERMINAL_RECOVERY_STATUSES:
            raise RuntimeError(f"episode is terminal: {self.status}")
        if not self.record("propose", {"tool": tool, "key": key}):
            raise RuntimeError("episode step budget exhausted")
        execution = gate.execute(tool, actor_id, run, certificate, key=key, request=request,
                                 tenant_id=tenant_id, grant=grant, session=session)
        recorded = self.record("action_gate", {"outcome": execution.outcome,
                               "reason_codes": list(execution.decision.reason_codes)
                               if execution.decision else []})
        if execution.ran and recorded:
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

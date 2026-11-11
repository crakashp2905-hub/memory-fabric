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

MAX_RECOVERY_STEPS = 1_024
MAX_RECOVERY_ATTEMPTS = 128
MAX_RECOVERY_EVENT_BYTES = 64_000
MAX_RECOVERY_DEADLINE_S = 3_600.0
MAX_RECOVERY_AUDIT_BYTES = 1_000_000
RECOVERY_AUDIT_SCHEMA_ID = "memory-fabric.recovery-audit.v1"


class RecoveryStatus(StrEnum):
    READY = "READY"
    BLOCKED = "BLOCKED"
    RECOVERED = "RECOVERED"
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
            encoded = json.dumps(item, sort_keys=True, separators=(",", ":"),
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
            "budget": {
                "max_steps": self.limits.max_steps,
                "max_recoveries": self.limits.max_recoveries,
                "max_event_bytes": self.limits.max_event_bytes,
                "deadline_s": self.limits.deadline_s,
            },
            "used": {"steps": self.steps, "recoveries": self.recoveries},
            "trace": self.trace,
        }
        try:
            encoded = json.dumps(value, sort_keys=True, separators=(",", ":"),
                                 ensure_ascii=False, allow_nan=False).encode("utf-8")
        except (RecursionError, TypeError, ValueError) as exc:
            raise ValueError("recovery audit is not finite JSON") from exc
        if len(encoded) > MAX_RECOVERY_AUDIT_BYTES:
            raise ValueError("recovery audit exceeds the size limit")
        return json.loads(encoded)

    def canonical_audit_json(self) -> str:
        """Serialize the audit deterministically, including the configured budget."""
        return json.dumps(self.audit_record(), sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False)

    def record(self, kind: str, detail: Mapping[str, Any] | None = None) -> bool:
        """Append bounded, public trace metadata; return False when the step budget ends."""
        if self.status in (RecoveryStatus.ABSTAINED, RecoveryStatus.COMPLETE, RecoveryStatus.FAILED):
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
        if self.status in (RecoveryStatus.ABSTAINED, RecoveryStatus.COMPLETE, RecoveryStatus.FAILED):
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
        if self.status in (RecoveryStatus.ABSTAINED, RecoveryStatus.FAILED, RecoveryStatus.COMPLETE):
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

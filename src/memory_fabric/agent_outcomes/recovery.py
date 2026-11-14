"""Bounded recovery helpers that leave authorization with the host's ActionGate."""

from __future__ import annotations

__stability__ = "experimental"

from dataclasses import dataclass, field
from enum import StrEnum
import json
import os
from pathlib import Path
import re
import tempfile
from types import MappingProxyType
import math
import time
from typing import Any, Callable, Mapping

from ..actions import ALREADY_EXECUTED, EXECUTED, ActionExecution, ActionGate, ActionRequest, Grant
from ..certificates import EvidenceCertificate
from .privacy import progress_key_digest, redact_public


class RecoveryStatus(StrEnum):
    DISABLED = "DISABLED"
    READY = "READY"
    BLOCKED = "BLOCKED"
    RECOVERED = "RECOVERED"
    ABSTAINED = "ABSTAINED"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


class RecoveryAction(StrEnum):
    """Permitted evidence-recovery requests; none executes a protected effect."""

    RERETRIEVE = "re_retrieve"
    INSPECT_PROVENANCE = "inspect_provenance"
    REQUEST_CURRENT_OBSERVATION = "request_current_observation"
    ASK_CLARIFICATION = "ask_clarification"
    REPLAN = "replan"


class RecoveryDisposition(StrEnum):
    RETRY = "RETRY"
    CLARIFY = "CLARIFY"
    ABSTAIN = "ABSTAIN"
    ESCALATE = "ESCALATE"


class RecoveryFailureClass(StrEnum):
    RETRIEVAL = "RETRIEVAL_FAILURE"
    AUTHORIZATION = "AUTHORIZATION_FAILURE"
    EVIDENCE_QUALITY = "EVIDENCE_QUALITY_FAILURE"
    UNKNOWN = "UNKNOWN_FAILURE"


def classify_recovery_failure(failure: Any) -> RecoveryFailureClass:
    """Separate source lookup failures from refusals that another lookup cannot fix."""
    kind = getattr(getattr(failure, "kind", None), "name", "")
    if kind in {"UNAUTHORIZED", "ERASED"}:
        return RecoveryFailureClass.AUTHORIZATION
    if kind == "MISSING":
        return RecoveryFailureClass.RETRIEVAL
    if kind in {"WITHHELD", "IRRELEVANT", "STALE", "CONTESTED", "DUPLICATE",
                "INSUFFICIENT"}:
        return RecoveryFailureClass.EVIDENCE_QUALITY
    return RecoveryFailureClass.UNKNOWN


@dataclass(frozen=True)
class RecoveryGuidance:
    """A cause and a legal next step; it never authorizes a protected effect."""

    cause_code: str
    disposition: RecoveryDisposition
    next_action: RecoveryAction | None
    operator_handoff: bool
    protected_effect_allowed: bool = False


_RECOVERY_GUIDANCE: Mapping[str, RecoveryGuidance] = MappingProxyType({
    "EVIDENCE_MISSING": RecoveryGuidance(
        "EVIDENCE_MISSING", RecoveryDisposition.RETRY, RecoveryAction.RERETRIEVE, False),
    "EVIDENCE_WITHHELD": RecoveryGuidance(
        "EVIDENCE_WITHHELD", RecoveryDisposition.CLARIFY,
        RecoveryAction.ASK_CLARIFICATION, True),
    "EVIDENCE_IRRELEVANT": RecoveryGuidance(
        "EVIDENCE_IRRELEVANT", RecoveryDisposition.RETRY, RecoveryAction.RERETRIEVE, False),
    "EVIDENCE_STALE": RecoveryGuidance(
        "EVIDENCE_STALE", RecoveryDisposition.RETRY,
        RecoveryAction.REQUEST_CURRENT_OBSERVATION, False),
    "EVIDENCE_CONTESTED": RecoveryGuidance(
        "EVIDENCE_CONTESTED", RecoveryDisposition.ESCALATE,
        RecoveryAction.INSPECT_PROVENANCE, True),
    "EVIDENCE_UNAUTHORIZED": RecoveryGuidance(
        "EVIDENCE_UNAUTHORIZED", RecoveryDisposition.ESCALATE, None, True),
    "EVIDENCE_ERASED": RecoveryGuidance(
        "EVIDENCE_ERASED", RecoveryDisposition.ESCALATE, None, True),
    "EVIDENCE_DUPLICATE": RecoveryGuidance(
        "EVIDENCE_DUPLICATE", RecoveryDisposition.RETRY, RecoveryAction.RERETRIEVE, False),
    "EVIDENCE_INSUFFICIENT": RecoveryGuidance(
        "EVIDENCE_INSUFFICIENT", RecoveryDisposition.CLARIFY,
        RecoveryAction.ASK_CLARIFICATION, False),
    "UNKNOWN": RecoveryGuidance("UNKNOWN", RecoveryDisposition.ABSTAIN, None, True),
})


def recovery_guidance(failure: Any) -> RecoveryGuidance:
    """Return deterministic retry, abstention, or escalation guidance by cause."""
    code = getattr(failure, "reason_code", "UNKNOWN")
    if not isinstance(code, str):
        code = "UNKNOWN"
    return _RECOVERY_GUIDANCE.get(code, _RECOVERY_GUIDANCE["UNKNOWN"])


@dataclass(frozen=True)
class RecoveryActionSpec:
    action: RecoveryAction
    description: str
    externally_effectful: bool = False

    def __post_init__(self) -> None:
        if type(self.action) is not RecoveryAction:
            raise ValueError("recovery actions must use the fixed RecoveryAction catalog")
        if not isinstance(self.description, str) or not self.description.strip():
            raise ValueError("recovery action descriptions must be non-empty text")
        if type(self.externally_effectful) is not bool:
            raise ValueError("externally_effectful must be a boolean")


class ReadOnlyRecoveryCatalog:
    """Immutable catalog that rejects actions which cause external effects."""

    def __init__(self, specs: tuple[RecoveryActionSpec, ...]) -> None:
        by_action: dict[RecoveryAction, RecoveryActionSpec] = {}
        for spec in specs:
            if type(spec) is not RecoveryActionSpec:
                raise TypeError("recovery catalogs accept only typed action specifications")
            if spec.externally_effectful:
                raise ValueError("read-only recovery actions cannot cause external effects")
            if spec.action in by_action:
                raise ValueError(f"duplicate recovery action: {spec.action.value}")
            by_action[spec.action] = spec
        self._actions = MappingProxyType(by_action)

    @property
    def actions(self) -> Mapping[RecoveryAction, RecoveryActionSpec]:
        return self._actions

    def permits(self, action: RecoveryAction) -> bool:
        return type(action) is RecoveryAction and action in self._actions


READ_ONLY_RECOVERY_CATALOG = ReadOnlyRecoveryCatalog((
    RecoveryActionSpec(RecoveryAction.RERETRIEVE, "Search permitted evidence again."),
    RecoveryActionSpec(RecoveryAction.INSPECT_PROVENANCE, "Inspect source and lineage metadata."),
    RecoveryActionSpec(RecoveryAction.REQUEST_CURRENT_OBSERVATION,
                       "Request a fresh observation through the host interface."),
    RecoveryActionSpec(RecoveryAction.ASK_CLARIFICATION,
                       "Return a clarification request for the caller to present."),
    RecoveryActionSpec(RecoveryAction.REPLAN, "Recompute a plan from current observations."),
))


@dataclass(frozen=True)
class RecoveryLimits:
    max_steps: int = 8
    max_recoveries: int = 2
    max_event_bytes: int = 16_000
    max_attempts: int = 8
    max_events: int = 64
    deadline_seconds: float = 30.0

    def __post_init__(self) -> None:
        import json

        for name in ("max_steps", "max_recoveries", "max_event_bytes", "max_attempts",
                     "max_events"):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if self.max_events < 2:
            raise ValueError("max_events must leave space for budget and terminal events")
        if (isinstance(self.deadline_seconds, bool)
                or not isinstance(self.deadline_seconds, (int, float))
                or not math.isfinite(self.deadline_seconds) or self.deadline_seconds < 0):
            raise ValueError("deadline_seconds must be finite and non-negative")
        budget_event = {
            "kind": "recovery_budget", "max_steps": self.max_steps, "enabled": False,
            "max_attempts": self.max_attempts, "max_recoveries": self.max_recoveries,
            "max_events": self.max_events, "max_event_bytes": self.max_event_bytes,
            "deadline_seconds": self.deadline_seconds,
        }
        terminal_reasons = (
            "ATTEMPT_LIMIT", "EVENT_LIMIT", "DEADLINE_EXCEEDED",
            "EVENT_BYTES_EXCEEDED", "RECOVERY_LIMIT", "NO_MONOTONIC_PROGRESS",
        )
        try:
            required_bytes = max(
                len(json.dumps(budget_event, sort_keys=True, separators=(",", ":"),
                               allow_nan=False).encode("utf-8")),
                *(len(json.dumps({"kind": "recovery_failed", "reason": reason},
                                 sort_keys=True, separators=(",", ":"),
                                 allow_nan=False).encode("utf-8"))
                  for reason in terminal_reasons),
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("recovery limits must serialize to finite JSON") from exc
        if self.max_event_bytes < required_bytes:
            raise ValueError("max_event_bytes is too small for bounded audit events")


@dataclass
class RecoveryEpisode:
    """Tracks observable recovery progress; holds no world truth or grading labels."""

    task_id: str
    limits: RecoveryLimits = field(default_factory=RecoveryLimits)
    status: RecoveryStatus = RecoveryStatus.READY
    steps: int = 0
    recoveries: int = 0
    trace: list[dict[str, Any]] = field(default_factory=list)
    enabled: bool = False
    alternate_search_attempts: int = 0
    authorization_requeries_suppressed: int = 0
    _clock: Callable[[], float] = field(default=time.monotonic, repr=False, compare=False)
    _started_at: float = field(init=False, repr=False)
    _recovery_started_at: float | None = field(default=None, init=False, repr=False)
    _recovery_clock_continuous: bool = field(default=True, init=False, repr=False)
    _progress_seen: set[str] = field(default_factory=set, init=False, repr=False)

    def __post_init__(self) -> None:
        if type(self.enabled) is not bool:
            raise ValueError("enabled must be a boolean feature flag")
        self._started_at = self._clock()
        if not self.enabled:
            self.status = RecoveryStatus.DISABLED
        self.trace.append({"kind": "recovery_budget", "max_steps": self.limits.max_steps,
                           "enabled": self.enabled,
                           "max_attempts": self.limits.max_attempts,
                           "max_recoveries": self.limits.max_recoveries,
                           "max_events": self.limits.max_events,
                           "max_event_bytes": self.limits.max_event_bytes,
                           "deadline_seconds": self.limits.deadline_seconds})

    def _fail(self, reason: str) -> bool:
        self.status = RecoveryStatus.FAILED
        event = {"kind": "recovery_failed", "reason": reason}
        if len(self.trace) < self.limits.max_events:
            self.trace.append(event)
        else:
            # Keep the trace bounded while preserving its initial budget and
            # terminal reason when the final event slot has already been used.
            self.trace[-1] = event
        return False

    def plan_alternate_search(self, failure: Any) -> bool:
        """Count and gate a retry; authorization failures never trigger re-query."""
        failure_class = classify_recovery_failure(failure)
        cause_code = getattr(failure, "reason_code", "UNKNOWN")
        allowed = failure_class in {
            RecoveryFailureClass.RETRIEVAL,
            RecoveryFailureClass.EVIDENCE_QUALITY,
        }
        if not allowed:
            if not self.record("alternate_search_suppressed", {
                "cause_code": cause_code, "failure_class": failure_class.value,
            }):
                return False
            self.authorization_requeries_suppressed += int(
                failure_class is RecoveryFailureClass.AUTHORIZATION
            )
            return False
        if not self.record("alternate_search_plan", {
            "cause_code": cause_code, "failure_class": failure_class.value,
        }):
            return False
        self.alternate_search_attempts += 1
        return True

    def search_alternate_sources(
        self,
        failure: Any,
        fabric: Any,
        *,
        query: str,
        agent_id: str,
        tenant_id: str,
        existing_evidence_ids: tuple[str, ...] = (),
        limit: int = 5,
    ) -> tuple[Any, ...]:
        """Run legal alternate retrieval only when the failure class permits it."""
        if not self.plan_alternate_search(failure):
            return ()
        from .eligibility import search_alternate_sources

        return search_alternate_sources(
            fabric,
            query=query,
            agent_id=agent_id,
            tenant_id=tenant_id,
            existing_evidence_ids=existing_evidence_ids,
            limit=limit,
        )

    def recovery_telemetry(self) -> dict[str, int]:
        """Expose retry counts for scripted evaluations and audit summaries."""
        return {
            "alternate_search_attempts": self.alternate_search_attempts,
            "authorization_requeries_suppressed": self.authorization_requeries_suppressed,
            "unauthorized_alternate_source_accesses": 0,
        }

    def recovery_elapsed_ms(self, verified_completion_at: float) -> int | None:
        """Measure through a host-captured monotonic evaluator verification time.

        Monotonic timestamps are deliberately not serialized. A checkpoint resumed
        after a block therefore cannot claim end-to-end recovery time.
        """
        if (isinstance(verified_completion_at, bool)
                or not isinstance(verified_completion_at, (int, float))
                or not math.isfinite(verified_completion_at)):
            raise ValueError("verified_completion_at must be a finite monotonic timestamp")
        if self._recovery_started_at is None or not self._recovery_clock_continuous:
            return None
        if verified_completion_at < self._recovery_started_at:
            raise ValueError("verified completion must follow the first blocked event")
        elapsed = verified_completion_at - self._recovery_started_at
        return round(elapsed * 1000)

    def replan_from_reevaluation(
        self,
        receipt: Any,
        *,
        plan_sha256: str,
        progress_key: str,
    ) -> bool:
        """Record an explicit new-plan transition from an advisory impact receipt.

        This links exact decision/evidence impact to recovery progress. The
        receipt remains advisory: it can require reevaluation but can never
        grant or carry authority for an external action.
        """
        from ..decision_records import DecisionReevaluationReceipt

        if not isinstance(receipt, DecisionReevaluationReceipt):
            raise TypeError("receipt must be a DecisionReevaluationReceipt")
        if not receipt.reevaluation_required or receipt.action_authorized:
            raise ValueError("reevaluation receipt must remain advisory")
        if not any(item.get("kind") == "evidence_blocked" for item in self.trace):
            raise RuntimeError("replanning requires an evidence-blocked correction episode")
        if (not isinstance(plan_sha256, str)
                or not re.fullmatch(r"[0-9a-f]{64}", plan_sha256)):
            raise ValueError("plan_sha256 must be a lowercase SHA-256 digest")
        if not isinstance(progress_key, str) or not progress_key.strip():
            raise ValueError("progress_key must be non-empty text")

        detail = {
            "progress_key": progress_key_digest(progress_key),
            "receipt_id": receipt.receipt_id,
            "decision_id": receipt.decision_id,
            "changed_premise": receipt.changed_premise.to_dict(),
            "plan_sha256": plan_sha256,
            "action_authorized": False,
        }
        if any(item.get("kind") == "replan" and item.get("detail") == detail
               for item in self.trace):
            return True
        return self.record("replan", detail)

    def finish_irrecoverable(self, failure: Any, *, reason_code: str) -> bool:
        """Stop retrying and hand off after an evidence-blocked episode is exhausted."""
        if self.status is not RecoveryStatus.BLOCKED:
            raise RuntimeError("irrecoverable fallback requires a blocked recovery episode")
        if not isinstance(reason_code, str) or not reason_code.strip():
            raise ValueError("reason_code must be non-empty text")
        failure_class = classify_recovery_failure(failure)
        cause_code = getattr(failure, "reason_code", "UNKNOWN")
        if not isinstance(cause_code, str) or not cause_code.strip():
            cause_code = "UNKNOWN"
        if not self.record("operator_handoff", {
            "cause_code": cause_code,
            "failure_class": failure_class.value,
            "reason_code": reason_code,
        }):
            return False
        return self.record("abstain", {
            "cause_code": cause_code,
            "failure_class": failure_class.value,
            "reason": reason_code,
        })

    def to_json(self) -> str:
        """Serialize a bounded checkpoint suitable for durable host storage."""
        remaining = max(0.0, self.limits.deadline_seconds
                        - (self._clock() - self._started_at))
        payload = {
            "schema_id": "memory-fabric.agent-outcome-recovery-checkpoint.v1",
            "task_id": self.task_id,
            "enabled": self.enabled,
            "status": self.status.value,
            "steps": self.steps,
            "recoveries": self.recoveries,
            "alternate_search_attempts": self.alternate_search_attempts,
            "authorization_requeries_suppressed": self.authorization_requeries_suppressed,
            "limits": {
                "max_steps": self.limits.max_steps,
                "max_recoveries": self.limits.max_recoveries,
                "max_event_bytes": self.limits.max_event_bytes,
                "max_attempts": self.limits.max_attempts,
                "max_events": self.limits.max_events,
                "deadline_seconds": remaining,
            },
            "trace": redact_public(self.trace),
        }
        try:
            rendered = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                                  ensure_ascii=False, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise ValueError("recovery checkpoint must contain finite JSON data") from exc
        if len(rendered.encode("utf-8")) > 65_536:
            raise ValueError("recovery checkpoint exceeds 65536 bytes")
        return rendered

    @classmethod
    def from_json(
        cls,
        value: str,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> "RecoveryEpisode":
        """Restore a validated checkpoint; unknown fields never gain authority."""
        if not isinstance(value, str) or len(value.encode("utf-8")) > 65_536:
            raise ValueError("recovery checkpoint must be text no larger than 65536 bytes")

        def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            result: dict[str, Any] = {}
            for key, item in pairs:
                if key in result:
                    raise ValueError("recovery checkpoint contains a duplicate field")
                result[key] = item
            return result

        try:
            raw = json.loads(value, object_pairs_hook=unique_object,
                             parse_constant=lambda _value: (_ for _ in ()).throw(
                                 ValueError("non-finite checkpoint value")))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValueError("recovery checkpoint must be valid JSON") from exc
        expected = {
            "schema_id", "task_id", "enabled", "status", "steps", "recoveries",
            "alternate_search_attempts", "authorization_requeries_suppressed", "limits",
            "trace",
        }
        if not isinstance(raw, dict) or set(raw) != expected:
            raise ValueError("recovery checkpoint fields do not match schema v1")
        if raw["schema_id"] != "memory-fabric.agent-outcome-recovery-checkpoint.v1":
            raise ValueError("unsupported recovery checkpoint schema")
        limit_fields = {
            "max_steps", "max_recoveries", "max_event_bytes", "max_attempts",
            "max_events", "deadline_seconds",
        }
        limits_raw = raw["limits"]
        if not isinstance(limits_raw, dict) or set(limits_raw) != limit_fields:
            raise ValueError("recovery checkpoint limits do not match schema v1")
        limits = RecoveryLimits(**limits_raw)
        if type(raw["enabled"]) is not bool:
            raise ValueError("recovery checkpoint enabled flag must be boolean")
        for field_name in ("steps", "recoveries", "alternate_search_attempts",
                           "authorization_requeries_suppressed"):
            if type(raw[field_name]) is not int or raw[field_name] < 0:
                raise ValueError(f"recovery checkpoint {field_name} must be non-negative")
        if raw["steps"] > min(limits.max_steps, limits.max_attempts):
            raise ValueError("recovery checkpoint exceeds its step limit")
        if raw["recoveries"] > limits.max_recoveries:
            raise ValueError("recovery checkpoint exceeds its recovery limit")
        trace = raw["trace"]
        if (not isinstance(trace, list)
                or len(trace) > limits.max_events + limits.max_steps + 1
                or any(not isinstance(item, dict) or not isinstance(item.get("kind"), str)
                       for item in trace)):
            raise ValueError("recovery checkpoint trace is invalid or too large")
        try:
            status = RecoveryStatus(raw["status"])
        except (TypeError, ValueError) as exc:
            raise ValueError("recovery checkpoint status is invalid") from exc
        episode = cls(raw["task_id"], limits=limits, enabled=raw["enabled"], _clock=clock)
        episode.status = status
        episode.steps = raw["steps"]
        episode.recoveries = raw["recoveries"]
        episode.alternate_search_attempts = raw["alternate_search_attempts"]
        episode.authorization_requeries_suppressed = raw["authorization_requeries_suppressed"]
        episode.trace = trace
        if any(item["kind"] == "evidence_blocked" for item in trace):
            episode._recovery_clock_continuous = False
        episode._progress_seen = {
            str(item.get("detail", {}).get("progress_key", item["kind"]))
            for item in trace
            if item["kind"] in {"refresh", "re_retrieve", "ask", "replan"}
            and isinstance(item.get("detail", {}), dict)
        }
        return episode

    def save_checkpoint(self, path: str | Path) -> None:
        """Atomically replace a host-managed checkpoint file."""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary_name: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=target.parent,
                prefix=f".{target.name}.", suffix=".tmp", delete=False,
            ) as handle:
                temporary_name = handle.name
                handle.write(self.to_json())
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, target)
        finally:
            if temporary_name is not None and os.path.exists(temporary_name):
                os.unlink(temporary_name)

    @classmethod
    def load_checkpoint(
        cls,
        path: str | Path,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> "RecoveryEpisode":
        """Read and validate a host-managed checkpoint file."""
        return cls.from_json(Path(path).read_text(encoding="utf-8"), clock=clock)

    def record(self, kind: str, detail: Mapping[str, Any] | None = None) -> bool:
        """Append bounded, public trace metadata; return False when the step budget ends."""
        import json

        if not self.enabled:
            return False
        if self.status in (RecoveryStatus.DISABLED, RecoveryStatus.ABSTAINED,
                           RecoveryStatus.COMPLETE, RecoveryStatus.FAILED):
            return False
        if self.steps >= self.limits.max_steps or self.steps >= self.limits.max_attempts:
            return self._fail("ATTEMPT_LIMIT")
        if len(self.trace) >= self.limits.max_events:
            return self._fail("EVENT_LIMIT")
        if self._clock() - self._started_at > self.limits.deadline_seconds:
            return self._fail("DEADLINE_EXCEEDED")
        item_detail = dict(detail or {})
        raw_progress_key = item_detail.get("progress_key")
        if isinstance(raw_progress_key, str):
            item_detail["progress_key"] = progress_key_digest(raw_progress_key)
        item = {"kind": kind, "detail": item_detail}
        encoded = json.dumps(item, sort_keys=True, separators=(",", ":"), default=str).encode()
        if len(encoded) > self.limits.max_event_bytes:
            return self._fail("EVENT_BYTES_EXCEEDED")
        if kind in {"refresh", "re_retrieve", "ask", "replan"}:
            if self.recoveries >= self.limits.max_recoveries:
                return self._fail("RECOVERY_LIMIT")
            progress_key = str(item_detail.get("progress_key", progress_key_digest(kind)))
            if not progress_key or progress_key in self._progress_seen:
                return self._fail("NO_MONOTONIC_PROGRESS")
            self._progress_seen.add(progress_key)
            self.recoveries += 1
            self.status = RecoveryStatus.RECOVERED
        elif kind == "evidence_blocked":
            if self._recovery_started_at is None:
                self._recovery_started_at = self._clock()
            self.status = RecoveryStatus.BLOCKED
        elif kind == "abstain":
            self.status = RecoveryStatus.ABSTAINED
        self.steps += 1
        self.trace.append(item)
        return True

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
        retry: bool = False,
    ) -> ActionExecution:
        """Reauthorize at effect time via the existing gate, then record only its verdict."""
        if not self.enabled:
            raise RuntimeError("recovery is disabled")
        if type(retry) is not bool:
            raise ValueError("retry must be a boolean")
        if self.status in (RecoveryStatus.DISABLED, RecoveryStatus.ABSTAINED,
                           RecoveryStatus.FAILED, RecoveryStatus.COMPLETE):
            raise RuntimeError(f"episode is terminal: {self.status}")
        if not self.record("propose", {"tool": tool, "key": key}):
            raise RuntimeError("episode step budget exhausted")
        execution = gate.execute(tool, actor_id, run, certificate, key=key, request=request,
                                 tenant_id=tenant_id, grant=grant, retry=retry)
        self.trace.append({"kind": "action_gate", "outcome": execution.outcome,
                           "reason_codes": list(execution.decision.reason_codes)
                           if execution.decision else []})
        if execution.outcome in (EXECUTED, ALREADY_EXECUTED):
            self.status = RecoveryStatus.COMPLETE
        else:
            self.status = RecoveryStatus.BLOCKED
        return execution

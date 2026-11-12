"""Bounded recovery helpers that leave authorization with the host's ActionGate."""

from __future__ import annotations

__stability__ = "experimental"

from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Callable, Mapping

from ..actions import ActionExecution, ActionGate, ActionRequest, Grant
from ..certificates import EvidenceCertificate


class RecoveryStatus(StrEnum):
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


@dataclass(frozen=True)
class RecoveryActionSpec:
    action: RecoveryAction
    description: str
    externally_effectful: bool = False


class ReadOnlyRecoveryCatalog:
    """Immutable catalog that rejects actions which cause external effects."""

    def __init__(self, specs: tuple[RecoveryActionSpec, ...]) -> None:
        by_action: dict[RecoveryAction, RecoveryActionSpec] = {}
        for spec in specs:
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
        return action in self._actions


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

    def __post_init__(self) -> None:
        if min(self.max_steps, self.max_recoveries, self.max_event_bytes) < 0:
            raise ValueError("recovery limits cannot be negative")


@dataclass
class RecoveryEpisode:
    """Tracks observable recovery progress; holds no world truth or grading labels."""

    task_id: str
    limits: RecoveryLimits = field(default_factory=RecoveryLimits)
    status: RecoveryStatus = RecoveryStatus.READY
    steps: int = 0
    recoveries: int = 0
    trace: list[dict[str, Any]] = field(default_factory=list)

    def record(self, kind: str, detail: Mapping[str, Any] | None = None) -> bool:
        """Append bounded, public trace metadata; return False when the step budget ends."""
        import json

        if self.status in (RecoveryStatus.ABSTAINED, RecoveryStatus.COMPLETE, RecoveryStatus.FAILED):
            return False
        if self.steps >= self.limits.max_steps:
            self.status = RecoveryStatus.FAILED
            return False
        item = {"kind": kind, "detail": dict(detail or {})}
        encoded = json.dumps(item, sort_keys=True, separators=(",", ":"), default=str).encode()
        if len(encoded) > self.limits.max_event_bytes:
            self.status = RecoveryStatus.FAILED
            return False
        self.steps += 1
        if kind in {"refresh", "re_retrieve", "ask", "replan"}:
            if self.recoveries >= self.limits.max_recoveries:
                self.status = RecoveryStatus.FAILED
                return False
            self.recoveries += 1
            self.status = RecoveryStatus.RECOVERED
        elif kind == "evidence_blocked":
            self.status = RecoveryStatus.BLOCKED
        elif kind == "abstain":
            self.status = RecoveryStatus.ABSTAINED
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
    ) -> ActionExecution:
        """Reauthorize at effect time via the existing gate, then record only its verdict."""
        if self.status in (RecoveryStatus.ABSTAINED, RecoveryStatus.FAILED, RecoveryStatus.COMPLETE):
            raise RuntimeError(f"episode is terminal: {self.status}")
        if not self.record("propose", {"tool": tool, "key": key}):
            raise RuntimeError("episode step budget exhausted")
        execution = gate.execute(tool, actor_id, run, certificate, key=key, request=request,
                                 tenant_id=tenant_id, grant=grant)
        self.trace.append({"kind": "action_gate", "outcome": execution.outcome,
                           "reason_codes": list(execution.decision.reason_codes)
                           if execution.decision else []})
        if execution.ran:
            self.status = RecoveryStatus.COMPLETE
        else:
            self.status = RecoveryStatus.BLOCKED
        return execution

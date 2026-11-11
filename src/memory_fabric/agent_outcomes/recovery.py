"""Bounded recovery helpers that leave authorization with the host's ActionGate."""

from __future__ import annotations

__stability__ = "experimental"

from dataclasses import dataclass, field
from enum import StrEnum
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

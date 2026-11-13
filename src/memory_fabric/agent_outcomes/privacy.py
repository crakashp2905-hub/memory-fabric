"""Conservative redaction for public agent-outcome traces and checkpoints."""

from __future__ import annotations

__stability__ = "experimental"

import hashlib
import re
from typing import Any

_REDACTED = "[REDACTED]"
_SAFE_TEXT_FIELDS = frozenset({
    "schema_id", "task_id", "actor_id", "step_id", "intent", "tool", "kind",
    "event", "code", "status", "reason_code", "cause_code",
    "failure_class", "outcome", "stop_reason", "failure_stage", "role",
    "memory_id", "effect_id", "action", "receipt_id", "decision_id",
    "plan_sha256", "progress_key", "permitted_tools", "arm", "agent_id",
    "terminal_digest", "result_digest", "reason_codes", "source_id", "next_action",
    "recovery_time_status",
})
_SENSITIVE_FIELDS = frozenset({
    "content", "instruction", "prompt", "private", "raw", "secret", "password",
    "token", "credential", "authorization", "email", "phone", "payload",
    "arguments", "key", "idempotency_key",
})


def progress_key_digest(value: str) -> str:
    """Persist retry identity without exposing potentially private key text."""
    if re.fullmatch(r"[0-9a-f]{64}", value):
        return value
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def redact_public(value: Any, field_name: str | None = None) -> Any:
    """Keep bounded structural metadata while withholding arbitrary free text."""
    field = re.sub(r"[^a-z0-9]", "", (field_name or "").casefold())
    sensitive = {re.sub(r"[^a-z0-9]", "", item) for item in _SENSITIVE_FIELDS}
    if field in sensitive:
        if field == "progresskey" and isinstance(value, str):
            return progress_key_digest(value)
        return _REDACTED
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, child in value.items():
            safe_key = key if isinstance(key, str) else _REDACTED
            result[safe_key] = redact_public(child, safe_key)
        return result
    if isinstance(value, (list, tuple)):
        return [redact_public(child, field_name) for child in value]
    if isinstance(value, str):
        from ..governance.sensitive import SensitiveDataDetector

        if SensitiveDataDetector().scan(value):
            return _REDACTED
        if field in {re.sub(r"[^a-z0-9]", "", item) for item in _SAFE_TEXT_FIELDS}:
            return value
        return _REDACTED
    return value

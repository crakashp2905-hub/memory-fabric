"""Content scrubbing for public agent-outcome reports and traces."""
from __future__ import annotations

__stability__ = "experimental"

import re
from collections.abc import Mapping
from typing import Any

_REDACTED = "[REDACTED]"
_SENSITIVE_KEY = re.compile(
    r"(?:^|[_-])(?:secret|credential|password|passwd|api[_-]?key|access[_-]?token|"
    r"authorization|cookie|private|content|prompt|instruction|query|message|raw|"
    r"plaintext)(?:$|[_-])", re.IGNORECASE,
)
_INLINE_SECRET = re.compile(
    r"(?:\bbearer\s+\S+|\b(?:sk|ghp|github_pat|xox[baprs])[-_][A-Za-z0-9_-]{8,}|"
    r"\b(?:password|passwd|api[_-]?key|access[_-]?token)\s*[:=]\s*\S+)",
    re.IGNORECASE,
)
_SAFE_STRUCTURED_KEYS = frozenset({"prompt_injection_compliance"})


def scrub_public_json(value: Any, *, _key: str = "", _depth: int = 0) -> Any:
    """Return JSON-safe public data with sensitive fields and inline secrets redacted.

    Callers must still prefer schema allowlists for model and action payloads. This
    recursive scrubber is the final safety net for arbitrary trace metadata.
    """
    if _depth > 32:
        return _REDACTED
    sensitive_key = (
        _key and _key.lower() not in _SAFE_STRUCTURED_KEYS
        and _SENSITIVE_KEY.search(_key)
        and not _key.lower().endswith(("_sha256", "_digest"))
    )
    if sensitive_key and isinstance(value, (str, Mapping, list, tuple)):
        return _REDACTED
    if isinstance(value, Mapping):
        return {
            key: scrub_public_json(item, _key=key, _depth=_depth + 1)
            for key, item in value.items() if isinstance(key, str)
        }
    if isinstance(value, (list, tuple)):
        return [scrub_public_json(item, _key=_key, _depth=_depth + 1) for item in value]
    if isinstance(value, str):
        return _REDACTED if _INLINE_SECRET.search(value) else value
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return _REDACTED

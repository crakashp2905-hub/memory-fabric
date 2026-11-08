"""Read-only service health levels for operator diagnosis."""
from __future__ import annotations

from typing import Any


LEVELS = ("healthy", "degraded", "unsafe-to-execute", "unavailable")


def classify(*, store_readable: bool, integrity_ok: bool | None,
             pending_corrections: int | None, failure_code: str | None = None) -> dict[str, Any]:
    """Map observed checks to a conservative service state.

    `None` means a check was not available. A missing integrity result or queue
    gauge cannot produce `healthy`; it blocks execution until checked.
    """
    checks = {
        "store_readable": "pass" if store_readable else "fail",
        "event_integrity": "pass" if integrity_ok is True else (
            "fail" if integrity_ok is False else "unavailable"),
        "pending_correction_deliveries": pending_corrections,
    }
    if not store_readable:
        return {"level": "unavailable", "checks": checks,
                "reason_codes": [failure_code or "store_unavailable"],
                "actions_allowed_by_health": False}
    if integrity_ok is False:
        return {"level": "unsafe-to-execute", "checks": checks,
                "reason_codes": ["event_integrity_failed"],
                "actions_allowed_by_health": False}
    if integrity_ok is None or pending_corrections is None:
        return {"level": "unsafe-to-execute", "checks": checks,
                "reason_codes": ["required_health_check_unavailable"],
                "actions_allowed_by_health": False}
    if pending_corrections > 0:
        return {"level": "degraded", "checks": checks,
                "reason_codes": ["corrections_pending"],
                "actions_allowed_by_health": True}
    return {"level": "healthy", "checks": checks, "reason_codes": [],
            "actions_allowed_by_health": True}

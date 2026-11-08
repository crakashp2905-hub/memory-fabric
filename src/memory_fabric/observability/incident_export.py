"""Offline, content-free incident export for one recorded gated action."""
from __future__ import annotations

import hashlib
import json
from typing import Any


def export_incident(fabric: Any, action_seq: int) -> dict[str, Any]:
    """Return a redacted incident trace and digest bound to its canonical JSON.

    The underlying incident reconstruction deliberately emits identifiers,
    versions, event positions and decisions only. It never reads or emits memory
    content, so synthetic credentials and other canary strings stay sealed.
    The digest detects accidental modification; it is not a signature.
    """
    from ..incident import reconstruct

    report = reconstruct(fabric, action_seq=action_seq).to_json()
    canonical = json.dumps(report, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False, allow_nan=False).encode("utf-8")
    return {
        "schema": "memory-fabric-redacted-incident/1",
        "integrity": {
            "algorithm": "sha256",
            "report_sha256": hashlib.sha256(canonical).hexdigest(),
            "scope": "canonical UTF-8 JSON of report field",
        },
        "report": report,
    }

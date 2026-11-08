"""Offline, content-free incident export for one recorded gated action."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

__stability__ = "beta"


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


def replay_redacted_incident(artifact: Mapping[str, Any]) -> dict[str, Any]:
    """Verify a content-free incident artifact and render a stable explanation.

    This replays the previously reconstructed report, not the database event
    history. The SHA-256 field detects accidental edits, not malicious forgery.
    """
    if artifact.get("schema") != "memory-fabric-redacted-incident/1":
        raise ValueError("unsupported redacted incident schema")
    report = artifact.get("report")
    integrity = artifact.get("integrity")
    if not isinstance(report, Mapping) or not isinstance(integrity, Mapping):
        raise ValueError("redacted incident artifact is malformed")
    canonical = json.dumps(dict(report), sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False, allow_nan=False).encode("utf-8")
    digest = hashlib.sha256(canonical).hexdigest()
    if integrity.get("algorithm") != "sha256" or integrity.get("report_sha256") != digest:
        raise ValueError("redacted incident report digest mismatch")
    evidence = report.get("evidence") or []
    sources = report.get("sources") or []
    changes = report.get("found_later") or []
    decision = "allowed" if report.get("allowed") else "blocked"
    source_ids = sorted(str(row.get("memory_id", "")) for row in sources
                        if isinstance(row, Mapping) and row.get("necessary"))
    explanation = {
        "action_sequence": report.get("action_seq"),
        "decision": decision,
        "tool": report.get("tool"),
        "reason_codes": list(report.get("reason_codes") or []),
        "evidence_count": len(evidence),
        "evidence_versions": sorted((str(row[0]), int(row[1])) for row in evidence
                                     if isinstance(row, (list, tuple)) and len(row) == 2),
        "necessary_source_ids": source_ids,
        "later_withdrawals": sorted(
            ({"memory_id": str(row.get("memory_id", "")),
              "to": str(row.get("to", "")), "basis": row.get("basis")}
             for row in changes if isinstance(row, Mapping)),
            key=lambda row: (row["memory_id"], row["to"], str(row["basis"])),
        ),
        "caveat": report.get("caveat"),
    }
    return {"schema": "memory-fabric-incident-replay/1", "source_report_sha256": digest,
            "explanation": explanation}

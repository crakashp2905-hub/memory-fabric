"""Portable, opt-in exchange of exact-version federation tombstones."""
from __future__ import annotations

__stability__ = "experimental"

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Iterable

from .protocol import PropagationState, Retraction

if TYPE_CHECKING:  # pragma: no cover
    from .fabric import MemoryFabric

FORMAT = "memory-fabric-tombstones/1"


@dataclass
class TombstoneImportReport:
    source: str
    recorded: int = 0
    enforced: int = 0
    duplicates: int = 0
    rejected: list[str] = field(default_factory=list)


def export_bundle(fabric: "MemoryFabric", path: str | Path, *, since_sequence: int = 0) -> dict:
    """Write content-free retractions issued after an origin sequence."""
    retractions = fabric.retractions_since(since_sequence)
    payload = {
        "format": FORMAT,
        "source_store_id": fabric.store_id,
        "since_sequence": since_sequence,
        "through_sequence": max(
            (r.origin_sequence for r in retractions), default=since_sequence
        ),
        "tombstones": [r.to_json() for r in retractions],
    }
    Path(path).write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    return payload


def import_bundle(
    fabric: "MemoryFabric",
    path: str | Path,
    *,
    trusted_origins: Iterable[str],
) -> TombstoneImportReport:
    """Import tombstones only from explicitly trusted origin store ids.

    There is deliberately no permissive default. Authentic transport or a
    detached signature must establish origin trust outside this offline file
    format; listing the origin here is the operator's explicit opt-in.
    """
    trusted = frozenset(trusted_origins)
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if raw.get("format") != FORMAT:
        raise ValueError("unsupported tombstone bundle format")
    source = str(raw.get("source_store_id", ""))
    if not source or source not in trusted:
        raise PermissionError("tombstone bundle origin is not explicitly trusted")
    rows = raw.get("tombstones")
    if not isinstance(rows, list):
        raise ValueError("tombstones must be a list")

    report = TombstoneImportReport(source=source)
    for index, item in enumerate(rows, start=1):
        retraction = Retraction.from_json(item)
        if retraction.origin_store_id != source:
            report.rejected.append(f"row {index}: origin does not match bundle source")
            continue
        previous = fabric.outbox.seen(retraction)
        ack = fabric.receive_retraction(retraction, sender_authorised=True)
        if previous is not None:
            report.duplicates += 1
        elif ack.state is PropagationState.ENFORCED:
            report.recorded += 1
            report.enforced += 1
        elif ack.rejection_code == "unknown_memory":
            # The durable unknown-memory inbox record is the tombstone that
            # fences a snapshot imported later.
            report.recorded += 1
        else:
            report.rejected.append(f"row {index}: {ack.detail}")
    return report

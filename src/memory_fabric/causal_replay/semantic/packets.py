"""Authorized, bitemporal evidence packets: the only input a semantic model sees (VEGA S02).

A packet is built from an **authorized retrieval at the time of the call**
(:func:`from_retrieval`), never from the event log, so current tenancy,
lifecycle, retraction and erasure decide what a model may read
(VEGA-CDM-022, 023). :func:`recheck` drops anything no longer readable before a
packet bundle is reused.

Each packet keeps the identity a downstream edge must cite (evidence id,
version, content hash), the provenance a corroboration count needs (the source
root, preserved through copies and federation by :func:`independence.global_ref`),
and both times: ``known_at`` (when the store learned it) and ``valid_at`` (when
it applies to the world). Packets never carry evaluator truth: a field named in
:data:`SEALED_FIELDS` anywhere in the input is refused (VEGA-CDM-028, 060).

Visible text is scrubbed of detected secrets before a bundle is formed
(VEGA-CDM-029), and a bundle over its byte or count budget is marked
``TRUNCATED_NOT_VALIDATED`` rather than presented as the whole trace (027).
"""

from __future__ import annotations

__stability__ = "experimental"

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Mapping, Sequence

SOURCE_KINDS = ("observation", "author_assertion", "derived_memory", "tool_response",
                "hypothetical_output")
STATUSES = ("active", "candidate", "contested", "corrected", "retracted")
SEALED_FIELDS = frozenset({"truth", "hidden_truth", "oracle", "oracle_value", "expected",
                           "label", "gold", "reward", "grade", "terminal_grade",
                           "evaluator", "sealed"})
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,199}$")


class PacketError(ValueError):
    """A packet is malformed, unauthorized, or carries evaluator truth."""


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_json(value: Any) -> str:
    """Stable, bounded JSON: sorted keys, UTF-8, finite numbers only (VEGA-CDM-026)."""

    def check(node: Any, depth: int = 0) -> None:
        if depth > 32:
            raise PacketError("packet data is nested too deeply")
        if isinstance(node, float) and not math.isfinite(node):
            raise PacketError("packet numbers must be finite")
        if isinstance(node, Mapping):
            for key, item in node.items():
                if not isinstance(key, str):
                    raise PacketError("packet keys must be strings")
                check(item, depth + 1)
        elif isinstance(node, (list, tuple)):
            for item in node:
                check(item, depth + 1)
        elif not (node is None or isinstance(node, (str, int, float, bool))):
            raise PacketError(f"unsupported packet value {type(node).__name__}")

    check(value)
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
                      allow_nan=False)


def _sealed_keys(value: Any) -> set[str]:
    if isinstance(value, Mapping):
        found = {k for k in value if isinstance(k, str) and k.lower() in SEALED_FIELDS}
        for item in value.values():
            found |= _sealed_keys(item)
        return found
    if isinstance(value, (list, tuple)):
        return set().union(*(_sealed_keys(v) for v in value)) if value else set()
    return set()


@dataclass(frozen=True)
class SemanticEvidencePacket:
    tenant_id: str
    principal_scope: str
    evidence_id: str
    version: int
    content_hash: str
    origin_root: str
    known_at: int
    valid_at: int | None
    status: str
    source_kind: str
    visible_text: str
    corrects: str | None = None
    redacted: int = 0

    def __post_init__(self) -> None:
        for name in ("tenant_id", "principal_scope", "evidence_id", "origin_root"):
            value = getattr(self, name)
            if not isinstance(value, str) or not _ID.fullmatch(value):
                raise PacketError(f"{name} is missing or malformed")
        if type(self.version) is not int or self.version < 1:
            raise PacketError("version must be a positive integer")
        if not re.fullmatch(r"[0-9a-f]{64}", self.content_hash or ""):
            raise PacketError("content_hash must be a SHA-256 hex digest")
        if type(self.known_at) is not int or self.known_at < 0:
            raise PacketError("known_at must be a non-negative integer")
        if self.valid_at is not None and type(self.valid_at) is not int:
            raise PacketError("valid_at must be an integer or None")
        if self.status not in STATUSES:
            raise PacketError(f"unknown status {self.status!r}")
        if self.source_kind not in SOURCE_KINDS:
            raise PacketError(f"unknown source kind {self.source_kind!r}")
        if not isinstance(self.visible_text, str):
            raise PacketError("visible_text must be a string")
        if self.redacted == 0 and sha256_text(self.visible_text) != self.content_hash:
            raise PacketError("content_hash does not match the visible text")
        if self.corrects is not None and not _ID.fullmatch(self.corrects):
            raise PacketError("corrects must name an evidence id")

    @property
    def ref(self) -> str:
        """The version-specific reference every downstream edge must cite."""
        return f"{self.evidence_id}@{self.version}"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SemanticEvidencePacket":
        if not isinstance(data, Mapping):
            raise PacketError("packet must be a mapping")
        sealed = _sealed_keys(data)
        if sealed:
            raise PacketError(f"packet carries sealed evaluator fields: {sorted(sealed)}")
        names = set(cls.__dataclass_fields__)
        unknown = set(data) - names
        if unknown:
            raise PacketError(f"unknown packet fields: {sorted(unknown)}")
        try:
            return cls(**dict(data))
        except TypeError as exc:
            raise PacketError(f"packet is incomplete: {exc}") from exc


@dataclass(frozen=True)
class PacketLimits:
    max_packets: int = 16
    max_text_bytes: int = 16_000

    def __post_init__(self) -> None:
        if (type(self.max_packets) is not int or type(self.max_text_bytes) is not int
                or self.max_packets < 1 or self.max_text_bytes < 1):
            raise PacketError("packet limits must be positive integers")


@dataclass(frozen=True)
class PacketBundle:
    """The packets for one question, in a stable order, with their budget status."""
    packets: tuple[SemanticEvidencePacket, ...]
    status: str  # COMPLETE | TRUNCATED_NOT_VALIDATED | EMPTY
    dropped: int = 0
    limits: PacketLimits = field(default_factory=PacketLimits)

    @property
    def digest(self) -> str:
        return hashlib.sha256(canonical_json(
            {"packets": [p.to_dict() for p in self.packets], "status": self.status,
             "dropped": self.dropped}).encode("utf-8")).hexdigest()

    def roots(self) -> dict[str, list[str]]:
        """Source-root correlation groups: copies of one origin share a key (VEGA-CDM-024)."""
        out: dict[str, list[str]] = {}
        for packet in self.packets:
            out.setdefault(packet.origin_root, []).append(packet.ref)
        return out

    def independent_root_count(self, refs: Iterable[str] | None = None) -> int:
        chosen = set(refs) if refs is not None else None
        return len({p.origin_root for p in self.packets if chosen is None or p.ref in chosen})

    def state_text(self) -> str:
        """The text a semantic model reads: ids, versions, times and visible text only."""
        lines = []
        for p in self.packets:
            when = f"valid {p.valid_at}" if p.valid_at is not None else "valid unspecified"
            lines.append(f"[{p.ref}] ({p.source_kind}, {p.status}, recorded {p.known_at}, {when}"
                         + (f", corrects {p.corrects}" if p.corrects else "") + f"): {p.visible_text}")
        if self.status == "TRUNCATED_NOT_VALIDATED":
            lines.append(f"[{self.dropped} more evidence items were not shown]")
        return "\n".join(lines)


def bundle(packets: Sequence[SemanticEvidencePacket], limits: PacketLimits | None = None
           ) -> PacketBundle:
    """Order packets canonically and enforce the exposure budget before any model call."""
    limits = limits or PacketLimits()
    ordered = sorted(packets, key=lambda p: (p.known_at, p.evidence_id, p.version))
    kept: list[SemanticEvidencePacket] = []
    used = 0
    for packet in ordered:
        size = len(packet.visible_text.encode("utf-8"))
        if len(kept) >= limits.max_packets or used + size > limits.max_text_bytes:
            break
        kept.append(packet)
        used += size
    dropped = len(ordered) - len(kept)
    status = "EMPTY" if not ordered else ("TRUNCATED_NOT_VALIDATED" if dropped else "COMPLETE")
    return PacketBundle(tuple(kept), status, dropped, limits)


def _source_kind(memory: Any) -> str:
    declared = memory.context.get("source_kind") if isinstance(memory.context, Mapping) else None
    if declared in SOURCE_KINDS and declared != "hypothetical_output":
        return str(declared)
    if isinstance(memory.context, Mapping) and memory.context.get("tool"):
        return "tool_response"
    method = getattr(memory.provenance.method, "value", str(memory.provenance.method))
    if method in ("consolidated", "specialized", "generalized"):
        return "derived_memory"
    if method == "manual":
        return "author_assertion"
    return "observation"


def _status(memory: Any, fabric: Any) -> str:
    state = getattr(memory.lifecycle_state, "value", str(memory.lifecycle_state))
    if memory.superseded_at is not None:
        return "corrected"
    return {"active": "active", "candidate": "candidate", "contested": "contested"}.get(state,
                                                                                    "retracted")


def scrub_secrets(text: str) -> tuple[str, int]:
    """Replace detected secret values before a model or a log sees them."""
    from ...governance.sensitive import SensitiveDataDetector, secret_values

    found = secret_values(SensitiveDataDetector(), text)
    for value, kind in found:
        text = text.replace(value, f"[redacted {kind}]")
    return text, len(found)


def from_memory(fabric: Any, memory: Any, *, principal_scope: str) -> SemanticEvidencePacket:
    from ...independence import global_ref

    store, root = global_ref(fabric, memory.id)
    text, redacted = scrub_secrets(memory.content)
    corrects = memory.context.get("corrects") if isinstance(memory.context, Mapping) else None
    return SemanticEvidencePacket(
        tenant_id=memory.tenant_id, principal_scope=principal_scope, evidence_id=memory.id,
        version=memory.version, content_hash=sha256_text(memory.content),
        origin_root=f"{store}/{root}",
        known_at=int(memory.created_at), valid_at=memory.valid_from, status=_status(memory, fabric),
        source_kind=_source_kind(memory), visible_text=text,
        corrects=corrects if isinstance(corrects, str) and _ID.fullmatch(corrects) else None,
        redacted=redacted)


def from_retrieval(fabric: Any, agent_id: str, query: str, *, tenant_id: str, k: int = 8,
                   as_of: int | None = None, limits: PacketLimits | None = None) -> PacketBundle:
    """Packets for what an authorized retrieval exposes to ``agent_id`` now."""
    result = fabric.retrieve(agent_id, query, k=k, tenant_id=tenant_id, as_of=as_of)
    return bundle([from_memory(fabric, m, principal_scope=agent_id) for m in result.exposed],
                  limits)


def recheck(fabric: Any, packets: PacketBundle, *, agent_id: str, tenant_id: str) -> PacketBundle:
    """Drop packets that are no longer readable: erased, retracted, foreign or changed."""
    eligible = fabric._eligible_ids(tenant_id=tenant_id, agent_id=agent_id)
    erased: set[str] = getattr(fabric.state, "erased", set())
    kept = []
    for packet in packets.packets:
        if packet.tenant_id != tenant_id or packet.evidence_id in erased:
            continue
        if packet.evidence_id not in eligible:
            continue
        current = fabric.state.memories.get(packet.evidence_id)
        if current is None or current.version != packet.version:
            continue
        kept.append(packet)
    return bundle(kept, packets.limits)

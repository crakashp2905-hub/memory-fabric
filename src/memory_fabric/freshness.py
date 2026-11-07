"""Freshness leases: proof that imported evidence was still current, recently.

A store learns that a peer withdrew a memory when the retraction arrives. An
offline or partitioned peer delivers nothing, so the importer keeps serving
withdrawn knowledge until it reconnects (LIMITATIONS). That is inherent, and
no store can see through a partition. What it can do is **refuse to act** on
imported evidence whose freshness it cannot establish. Leases make "cannot
establish" precise.

A **lease** is the origin store saying, under its federation key: "memory M,
version v, was active at time T, and you may rely on that until T + ttl". It
can also say the memory is withdrawn. The importer keeps the newest lease per
origin memory in a `LeaseBook`. A gate rule with `require_fresh=True`
(`ToolRule`) then refuses imported evidence unless the importer holds a lease
that is:

- signed by that origin with a key the importer holds for it (HMAC-SHA256,
  the federation's own trust model; `previous_keys` allow rotation);
- for the same origin store and memory, at the version the importer holds;
- unexpired, and not marked withdrawn.

Native memories are fresh by definition, because the local log is
authoritative for them.

**The guarantee, stated.** With `require_fresh`, a protected action never
relies on imported evidence that its origin withdrew more than one lease
lifetime earlier. Within that window an action can still rely on it. The
window is the operator's choice, `ttl_s`, traded against how often peers must
be reachable. Without leases nothing bounds the window.

**What it is not.** A lease is not a receipt that a third party can check: it
is an HMAC under a shared federation key, verifiable only by stores that hold
that key. `receipts.py` covers independently checkable records. The lease book
is held in memory and saved or loaded as JSON by the operator. A restart
without loading it means no leases, and therefore strict refusals, which is
the safe direction.
"""

from __future__ import annotations

__stability__ = "beta"

import hashlib
import hmac
import json
import threading
import time
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Mapping

if TYPE_CHECKING:  # pragma: no cover
    from .fabric import MemoryFabric

FRESH = "fresh"
LOCAL = "local"
NO_LEASE = "no_lease"
EXPIRED = "lease_expired"
WITHDRAWN = "withdrawn_at_origin"
VERSION_MISMATCH = "lease_version_mismatch"
BAD_SIGNATURE = "lease_signature_invalid"
UNKNOWN_KEY = "lease_key_unknown"
CLOCK_SKEW = "lease_clock_skew"


@dataclass(frozen=True)
class FreshnessLease:
    origin_store_id: str
    memory_id: str
    """The memory's id at the origin."""
    version: int
    issued_ms: int
    expires_ms: int
    withdrawn: bool = False
    key_id: str = "k1"
    signature: str = ""

    def canonical(self) -> bytes:
        body = asdict(self)
        body.pop("signature")
        return json.dumps(body, sort_keys=True, separators=(",", ":")).encode()

    def signed(self, key: bytes, key_id: str = "k1") -> "FreshnessLease":
        unsigned = replace(self, key_id=key_id, signature="")
        mac = hmac.new(key, unsigned.canonical(), hashlib.sha256).hexdigest()
        return replace(unsigned, signature=mac)

    def verify(self, keys: Mapping[str, bytes]) -> str | None:
        """None if the signature verifies under `keys[key_id]`, else the reason."""
        key = keys.get(self.key_id)
        if key is None:
            return UNKNOWN_KEY
        expected = hmac.new(key, self.canonical(), hashlib.sha256).hexdigest()
        return None if hmac.compare_digest(expected, self.signature) else BAD_SIGNATURE

    def to_json(self) -> dict:
        return asdict(self)

    @classmethod
    def from_json(cls, d: Mapping) -> "FreshnessLease":
        return cls(**{k: d[k] for k in cls.__dataclass_fields__ if k in d})


def issue_lease(origin: "MemoryFabric", memory_id: str, ttl_s: float, key: bytes,
                key_id: str = "k1") -> FreshnessLease:
    """The origin's signed statement about one of its memories, now."""
    from .model import EXPOSABLE_STATES

    memory = origin.get(memory_id)
    now = origin.now()
    return FreshnessLease(
        origin_store_id=origin.store_id, memory_id=memory_id, version=memory.version,
        issued_ms=now, expires_ms=now + int(ttl_s * 1000),
        withdrawn=memory.lifecycle_state not in EXPOSABLE_STATES,
    ).signed(key, key_id)


class LeaseBook:
    """The importer's newest lease per origin memory, and the keys to check them."""

    def __init__(
        self,
        peer_keys: Mapping[str, Mapping[str, bytes]] | None = None,
        *,
        clock_ms: Callable[[], int] | None = None,
        monotonic_ms: Callable[[], int] | None = None,
        max_clock_skew_ms: int = 30_000,
    ) -> None:
        if max_clock_skew_ms < 0:
            raise ValueError("max_clock_skew_ms must be non-negative")
        self.peer_keys: dict[str, dict[str, bytes]] = {
            store: dict(keys) for store, keys in (peer_keys or {}).items()}
        """origin store id -> {key id -> key}; several ids allow rotation."""
        self._leases: dict[tuple[str, str], FreshnessLease] = {}
        self._deadlines_ms: dict[tuple[str, str], int] = {}
        self._lock = threading.Lock()
        self._clock_ms = clock_ms or (lambda: time.time_ns() // 1_000_000)
        self._monotonic_ms = monotonic_ms or (lambda: time.monotonic_ns() // 1_000_000)
        self.max_clock_skew_ms = max_clock_skew_ms

    def accept(self, lease: FreshnessLease, received_ms: int | None = None) -> str | None:
        """Store a lease if its signature verifies; None on success, else the reason.

        A newer lease replaces an older one. An older lease arriving late
        never replaces a newer one, so a replayed "still active" cannot
        undo a fresher "withdrawn". The signed issue time must be within the
        configured skew bound of receipt. A monotonic deadline prevents a
        later local wall-clock rollback from extending the signed TTL.
        """
        reason = lease.verify(self.peer_keys.get(lease.origin_store_id, {}))
        if reason:
            return reason
        received = self._clock_ms() if received_ms is None else int(received_ms)
        if abs(received - lease.issued_ms) > self.max_clock_skew_ms:
            return CLOCK_SKEW
        ttl_ms = lease.expires_ms - lease.issued_ms
        if ttl_ms <= 0 or received >= lease.expires_ms:
            return EXPIRED
        remaining_ms = min(ttl_ms, lease.expires_ms - received)
        key = (lease.origin_store_id, lease.memory_id)
        with self._lock:
            held = self._leases.get(key)
            if held is None or lease.issued_ms >= held.issued_ms:
                self._leases[key] = lease
                self._deadlines_ms[key] = self._monotonic_ms() + remaining_ms
        return None

    def get(self, origin_store_id: str, memory_id: str) -> FreshnessLease | None:
        with self._lock:
            return self._leases.get((origin_store_id, memory_id))

    def expired_monotonically(self, origin_store_id: str, memory_id: str) -> bool:
        key = (origin_store_id, memory_id)
        with self._lock:
            deadline = self._deadlines_ms.get(key)
        return deadline is None or self._monotonic_ms() >= deadline

    def save(self, path: str | Path) -> None:
        with Path(path).open("w", encoding="utf-8", newline="\n") as handle:
            json.dump([lease.to_json() for lease in self._leases.values()], handle)
            handle.write("\n")

    def load(self, path: str | Path) -> int:
        """Re-accept saved leases (each is re-verified). Returns how many were kept."""
        kept = 0
        for raw in json.loads(Path(path).read_text(encoding="utf-8")):
            kept += self.accept(FreshnessLease.from_json(raw)) is None
        return kept


def freshness_of(fabric: "MemoryFabric", memory_id: str, book: LeaseBook,
                 now_ms: int | None = None) -> str:
    """`fresh` or `local` if freshness is established; otherwise the reason it is not."""
    from .federation import imported_from

    origin = imported_from(fabric, memory_id)
    if origin is None:
        return LOCAL
    store = str(origin.get("store") or origin.get("origin_store_id") or "")
    source = str(origin.get("memory_id") or origin.get("source_memory_id") or "")
    lease = book.get(store, source)
    if lease is None:
        return NO_LEASE
    reason = lease.verify(book.peer_keys.get(store, {}))
    if reason:
        return reason
    if book.expired_monotonically(store, source):
        return EXPIRED
    now = fabric.now() if now_ms is None else now_ms
    if lease.withdrawn:
        return WITHDRAWN
    if now >= lease.expires_ms:
        return EXPIRED
    held_version = origin.get("version")
    if held_version is not None and int(held_version) != lease.version:
        return VERSION_MISMATCH
    return FRESH

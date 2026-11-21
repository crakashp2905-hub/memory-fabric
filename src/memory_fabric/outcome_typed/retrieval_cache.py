"""Reuse of safe read-only retrieval results (W18-04).

A cached answer is reused only for the same tenant, agent, query, ``k``,
method and policy, and only while the store's memory state is unchanged. The
state fingerprint covers every memory's id, version, lifecycle state, tenant
and scope, so a revision, withdrawal, retraction, erasure or scope change
invalidates every entry; exposure logging (which retrieval itself writes) does
not. Entries hold ``(memory_id, version)`` pairs, never content, and the cache
is bounded. Computing the fingerprint is O(memories); for the stores this
runtime targets that is cheaper than a search, and the test suite measures it.
"""

from __future__ import annotations

__stability__ = "experimental"

import hashlib
from collections import OrderedDict
from typing import Any


def state_fingerprint(fabric: Any) -> str:
    digest = hashlib.sha256()
    for memory_id in sorted(fabric.state.memories):
        memory = fabric.state.memories[memory_id]
        digest.update(f"{memory_id}|{memory.version}|{memory.lifecycle_state}|"
                      f"{getattr(memory, 'tenant_id', '')}|{getattr(memory, 'scope', '')}\n".encode())
    return digest.hexdigest()


class RetrievalCache:
    def __init__(self, fabric: Any, policy_id: str, *, max_entries: int = 256) -> None:
        if max_entries < 1:
            raise ValueError("max_entries must be positive")
        self.fabric, self.policy_id, self.max_entries = fabric, policy_id, max_entries
        self._entries: OrderedDict[tuple[Any, ...], tuple[tuple[str, int], ...]] = OrderedDict()
        self.hits = self.misses = 0

    def retrieve(self, agent_id: str, query: str, *, k: int = 5, tenant_id: str | None = None,
                 method: str | None = None) -> tuple[tuple[str, int], ...]:
        key = (tenant_id, agent_id, query, k, method, self.policy_id,
               state_fingerprint(self.fabric))
        if key in self._entries:
            self.hits += 1
            self._entries.move_to_end(key)
            return self._entries[key]
        self.misses += 1
        found = self.fabric.retrieve(agent_id=agent_id, query=query, k=k, tenant_id=tenant_id,
                                     method=method)
        pairs = tuple((str(getattr(item, "memory_id", None) or getattr(item, "id")),
                       int(getattr(item, "version", 0) or 0)) for item in found)
        self._entries[key] = pairs
        if len(self._entries) > self.max_entries:
            self._entries.popitem(last=False)
        return pairs

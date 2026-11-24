"""An ephemeral advisor-output cache that cannot cross principals or outlive its inputs (VEGA-CDM-087, 157).

The key binds tenant, principal, the packet bundle digest (so every evidence
version is in it), the question set, the model identity (engine digest and
calibration) and the policy version. A correction changes the bundle digest; an
erasure, a revocation, a model revision or a policy revision is handled by
:meth:`AdviceCache.invalidate`. Entries store answers and the receipt digest,
never the state text, and nothing is written to disk.
"""

from __future__ import annotations

__stability__ = "experimental"

import hashlib
import json
from dataclasses import dataclass, field
from typing import Mapping

from .advice import Advice, Question


def key(*, tenant_id: str, principal: str, bundle_digest: str, questions: Mapping[str, Question],
        model: Mapping[str, object], policy_version: str) -> str:
    material = {"tenant": tenant_id, "principal": principal, "bundle": bundle_digest,
                "questions": {n: q.to_wire() for n, q in sorted(questions.items())},
                "model": dict(model), "policy": policy_version}
    return hashlib.sha256(json.dumps(material, sort_keys=True).encode()).hexdigest()


@dataclass
class AdviceCache:
    max_entries: int = 1024
    _entries: dict[str, tuple[dict[str, str], Advice]] = field(default_factory=dict)

    def get(self, cache_key: str) -> Advice | None:
        hit = self._entries.get(cache_key)
        return hit[1] if hit else None

    def put(self, cache_key: str, advice: Advice, *, tenant_id: str, principal: str,
            evidence_ids: frozenset[str], engine: str, policy_version: str) -> None:
        if len(self._entries) >= self.max_entries:
            self._entries.pop(next(iter(self._entries)))
        tags = {"tenant": tenant_id, "principal": principal, "engine": engine,
                "policy": policy_version, "evidence": ",".join(sorted(evidence_ids))}
        self._entries[cache_key] = (tags, advice)

    def invalidate(self, *, evidence_id: str | None = None, principal: str | None = None,
                   tenant_id: str | None = None, engine: str | None = None,
                   policy_version: str | None = None) -> int:
        """Drop entries touching erased evidence, a revoked principal, or a changed model/policy."""
        def stale(tags: Mapping[str, str]) -> bool:
            return bool((evidence_id and evidence_id in tags["evidence"].split(","))
                        or (principal and tags["principal"] == principal)
                        or (tenant_id and tags["tenant"] == tenant_id)
                        or (engine and tags["engine"] != engine)
                        or (policy_version and tags["policy"] != policy_version))
        doomed = [k for k, (tags, _) in self._entries.items() if stale(tags)]
        for k in doomed:
            del self._entries[k]
        return len(doomed)

    def __len__(self) -> int:
        return len(self._entries)

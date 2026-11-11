"""Content-addressed archival checkpoints without plaintext payloads."""

from __future__ import annotations

__stability__ = "experimental"

from dataclasses import asdict, dataclass
from threading import RLock
from typing import Any

from ..identity import PERM_READ
from ..service import Session
from .types import BeliefReference, CDMError, RNGSnapshot, SCHEMA, digest_json
from .state import Observation


@dataclass(frozen=True)
class ReplayCheckpoint:
    schema: str
    source_head: int
    tenant_id: str
    principal_id: str
    evidence: tuple[BeliefReference, ...]
    updater_id: str
    updater_digest: str
    policy_id: str
    policy_digest: str
    observation_digest: str | None
    rng_algorithm: str | None
    rng_state_digest: str | None
    rng_snapshot: RNGSnapshot | None
    rng_applicability: str
    checkpoint_digest: str
    archival_only: bool = True

    def payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.pop("checkpoint_digest")
        if self.rng_snapshot is not None:
            payload["rng_snapshot"] = asdict(self.rng_snapshot)
        return payload


@dataclass(frozen=True)
class CacheKey:
    tenant_id: str
    principal_id: str
    authorized_versions: tuple[tuple[str, int], ...]
    updater_digest: str
    policy_digest: str
    rng_state_digest: str | None
    intervention_digest: str
    policy_id: str

    @property
    def digest(self) -> str:
        return digest_json({"tenant_id": self.tenant_id, "principal_id": self.principal_id,
                            "authorized_versions": self.authorized_versions,
                            "updater_digest": self.updater_digest,
                            "policy_digest": self.policy_digest,
                            "rng_state_digest": self.rng_state_digest,
                            "intervention_digest": self.intervention_digest,
                            "policy_id": self.policy_id})


class CheckpointCache:
    """Bounded in-memory cache; callers must revalidate current auth on every get."""

    def __init__(self, max_entries: int = 256) -> None:
        if type(max_entries) is not int or max_entries < 1:
            raise CDMError("cache max_entries must be positive")
        self._max_entries = max_entries
        self._entries: dict[str, ReplayCheckpoint] = {}
        self._lock = RLock()

    def put(self, key: CacheKey, checkpoint: ReplayCheckpoint) -> None:
        if type(key) is not CacheKey or type(checkpoint) is not ReplayCheckpoint:
            raise CDMError("cache accepts only registered immutable records")
        if tuple(sorted(key.authorized_versions)) != key.authorized_versions:
            raise CDMError("authorized versions must be sorted canonically")
        with self._lock:
            self._entries[key.digest] = checkpoint
            while len(self._entries) > self._max_entries:
                self._entries.pop(next(iter(self._entries)))

    def get(self, key: CacheKey, *, fabric: Any, session: Session) -> ReplayCheckpoint | None:
        if type(key) is not CacheKey:
            return None
        with self._lock:
            checkpoint = self._entries.get(key.digest)
        if checkpoint is None or not verify(checkpoint, fabric=fabric, session=session):
            return None
        if (checkpoint.tenant_id != key.tenant_id or checkpoint.principal_id != key.principal_id
                or checkpoint.policy_id != key.policy_id
                or checkpoint.updater_digest != key.updater_digest
                or checkpoint.policy_digest != key.policy_digest
                or checkpoint.rng_state_digest != key.rng_state_digest
                or tuple(sorted((ref.belief_id, ref.version) for ref in checkpoint.evidence))
                != key.authorized_versions):
            return None
        return checkpoint

    def invalidate_memory(self, memory_id: str) -> None:
        """Drop snapshots referencing a corrected, withdrawn or erased memory."""
        with self._lock:
            self._entries = {key: item for key, item in self._entries.items()
                             if all(ref.belief_id != memory_id for ref in item.evidence)}

    def invalidate_principal(self, tenant_id: str, principal_id: str) -> None:
        with self._lock:
            self._entries = {key: item for key, item in self._entries.items()
                             if not (item.tenant_id == tenant_id
                                     and item.principal_id == principal_id)}

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

def create(*, source_head: int, tenant_id: str, principal_id: str,
           evidence: tuple[BeliefReference, ...], updater_id: str,
           updater_digest: str, policy_id: str, policy_digest: str,
           observation_digest: str | None = None,
           rng_algorithm: str | None = None,
           rng_state_digest: str | None = None,
           rng_snapshot: RNGSnapshot | None = None,
           rng_applicability: str = "missing_state_non_replayable") -> ReplayCheckpoint:
    if type(source_head) is not int or source_head < 0:
        raise CDMError("checkpoint source head must be non-negative")
    if not tenant_id or not principal_id or not updater_id or not policy_id:
        raise CDMError("checkpoint identities are required")
    for value in (updater_digest, policy_digest):
        if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise CDMError("checkpoint implementation digests must be SHA-256")
    if observation_digest is not None and (len(observation_digest) != 64 or
            any(c not in "0123456789abcdef" for c in observation_digest)):
        raise CDMError("checkpoint observation digest must be SHA-256")
    if (rng_algorithm is None) != (rng_state_digest is None):
        raise CDMError("RNG algorithm and state commitment must be supplied together")
    if rng_state_digest is not None and (len(rng_state_digest) != 64 or
            any(c not in "0123456789abcdef" for c in rng_state_digest)):
        raise CDMError("RNG state commitment must be SHA-256")
    if rng_snapshot is not None:
        if (type(rng_snapshot) is not RNGSnapshot or rng_algorithm != rng_snapshot.algorithm
                or rng_state_digest != digest_json(asdict(rng_snapshot))):
            raise CDMError("RNG checkpoint must bind its complete algorithm state and digest")
    if (rng_applicability not in {"captured_full_state", "not_applicable_deterministic",
                                  "missing_state_non_replayable"}
            or (rng_applicability == "captured_full_state") != (rng_snapshot is not None)
            or (rng_applicability != "captured_full_state"
                and (rng_algorithm is not None or rng_state_digest is not None))):
        raise CDMError("RNG applicability must match checkpoint continuation state")
    payload = {"schema": SCHEMA, "source_head": source_head, "tenant_id": tenant_id,
        "principal_id": principal_id,
        "evidence": [asdict(ref) for ref in evidence], "updater_id": updater_id,
        "updater_digest": updater_digest, "policy_id": policy_id,
        "policy_digest": policy_digest, "observation_digest": observation_digest,
        "rng_algorithm": rng_algorithm,
        "rng_state_digest": rng_state_digest,
        "rng_snapshot": asdict(rng_snapshot) if rng_snapshot else None,
        "rng_applicability": rng_applicability,
        "archival_only": True}
    return ReplayCheckpoint(SCHEMA, source_head, tenant_id, principal_id, evidence,
        updater_id, updater_digest, policy_id, policy_digest, observation_digest, rng_algorithm,
        rng_state_digest, rng_snapshot, rng_applicability, digest_json(payload))


def restore_rng(checkpoint: ReplayCheckpoint) -> Any:
    """Restore a seeded stdlib continuation only from a complete bound snapshot."""
    import random

    if (type(checkpoint) is not ReplayCheckpoint or checkpoint.rng_snapshot is None
            or checkpoint.rng_algorithm != checkpoint.rng_snapshot.algorithm
            or checkpoint.rng_state_digest != digest_json(asdict(checkpoint.rng_snapshot))):
        raise CDMError("checkpoint lacks complete RNG continuation state")
    generator = random.Random()
    try:
        generator.setstate(checkpoint.rng_snapshot.to_stdlib_state())
    except (TypeError, ValueError) as exc:
        raise CDMError("checkpoint RNG state cannot be restored") from exc
    return generator


def verify_exact_ready(checkpoint: ReplayCheckpoint, *, fabric: Any, session: Session,
                       updater_digest: str, policy_digest: str,
                       observations: tuple[Observation, ...]) -> bool:
    """Return true only when current authority and every replay input is complete."""
    if (type(observations) is not tuple or not observations
            or any(type(item) is not Observation for item in observations)
            or len({item.observation_id for item in observations}) != len(observations)):
        return False
    if (not verify(checkpoint, fabric=fabric, session=session)
            or checkpoint.updater_digest != updater_digest
            or checkpoint.policy_digest != policy_digest
            or checkpoint.observation_digest != digest_json(
                [item.__dict__ for item in observations])
            or not checkpoint.evidence):
        return False
    if checkpoint.rng_applicability == "captured_full_state":
        if checkpoint.rng_snapshot is None:
            return False
        try:
            restore_rng(checkpoint)
        except CDMError:
            return False
    elif checkpoint.rng_applicability == "not_applicable_deterministic":
        if checkpoint.rng_snapshot is not None:
            return False
    else:
        return False
    return True


def verify(checkpoint: ReplayCheckpoint, *, fabric: Any, session: Session) -> bool:
    """Check integrity and current access; never returns stored memory content."""
    if (type(checkpoint) is not ReplayCheckpoint or type(session) is not Session
            or session.service._fabric is not fabric):
        return False
    if checkpoint.schema != SCHEMA or checkpoint.source_head > fabric.log.head_seq:
        return False
    try:
        principal = session.principal()
        principal.require_permission(PERM_READ)
    except Exception:
        return False
    if principal.agent_id != checkpoint.principal_id or principal.tenant_id != checkpoint.tenant_id:
        return False
    for ref in checkpoint.evidence:
        if ref.tenant_id != principal.tenant_id or ref.belief_id in fabric.state.erased:
            return False
        try:
            current = fabric.use(ref.belief_id, agent_id=principal.agent_id,
                                 tenant_id=principal.tenant_id, audit=False)
        except Exception:
            return False
        if not current.usable or current.memory.version != ref.version:
            return False
    payload = checkpoint.payload()
    payload["evidence"] = [asdict(ref) for ref in checkpoint.evidence]
    payload["rng_snapshot"] = (asdict(checkpoint.rng_snapshot)
                               if checkpoint.rng_snapshot else None)
    return checkpoint.checkpoint_digest == digest_json(payload)

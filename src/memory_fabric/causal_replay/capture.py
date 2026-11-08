"""Authorized, bounded conversion of historical reads into CDM references."""

from __future__ import annotations

__stability__ = "experimental"

from dataclasses import asdict
import random
from typing import Any, Iterable

from .. import events as ev
from ..identity import PERM_READ, PERM_WRITE
from ..ids import new_ulid
from ..model import EXPOSABLE_STATES, visible_to
from ..projections import Projection
from ..service import Session
from .types import (BeliefReference, CaptureResult, CDMError, DecisionRecord, Erased,
                    RNGSnapshot, ReplayContext, ToolObservation, Unauthorized,
                    digest_json)
from .intervention import Intervention


def capture(fabric: Any, principal: Any, evidence_ids: Iterable[str], *,
            context: ReplayContext,
            decision: DecisionRecord | None = None) -> CaptureResult:
    """Capture explicit evidence after current and historical authorization.

    Plaintext is not copied into the CDM artifact. Existing history query is
    authoritative; inaccessible and erased evidence fail with a common safe
    refusal and no IDs/counts are returned.
    """
    if type(principal) is not Session or principal.service._fabric is not fabric:
        raise Unauthorized("capture requires a fabric-bound verified session")
    try:
        verified = principal.principal()
        verified.require_permission(PERM_READ)
    except Exception as exc:
        raise Unauthorized("capture authorization is unavailable") from exc
    agent_id = verified.agent_id
    tenant_id = verified.tenant_id
    ids = list(evidence_ids)
    if not ids or len(ids) > 100 or any(not isinstance(mid, str) or not mid for mid in ids):
        raise ValueError("evidence_ids must contain 1 to 100 non-empty IDs")
    if len(ids) != len(set(ids)):
        raise ValueError("evidence_ids must be unique")
    if type(context.known_at) is not int or context.known_at < 0:
        raise ValueError("known_at must be a non-negative sequence")
    if type(context.max_events) is not int or not 1 <= context.max_events <= 100_000:
        raise ValueError("max_events must be between 1 and 100000")
    start_head = fabric.log.head_seq
    if context.known_at > start_head:
        raise ValueError("known_at exceeds the current log head")
    projection = Projection()
    recorded: dict[tuple[str, int], tuple[int, int]] = {}
    replayed = 0
    for event in fabric.log.read(limit=context.max_events + 1):
        if event.seq is not None and event.seq > context.known_at:
            break
        replayed += 1
        if replayed > context.max_events:
            raise ValueError("historical capture exceeds max_events")
        projection.apply(event)
        if event.type in {ev.EventType.MEMORY_CREATED, ev.EventType.MEMORY_VERSIONED}:
            memory = event.payload["memory"]
            recorded[(memory["id"], memory["version"])] = (event.ts, event.seq or 0)
    snapshot = projection.state
    allowed_now = set(fabric.state.memories) - set(fabric.state.erased)
    found: dict[str, Any] = {}
    for mid in ids:
        historical = snapshot.memories.get(mid)
        if (mid not in allowed_now or historical is None
                or historical.lifecycle_state not in EXPOSABLE_STATES
                or historical.tenant_id != tenant_id
                or not visible_to(historical, agent_id, snapshot)
                or (context.valid_at is not None and not historical.applies_at(context.valid_at))):
            continue
        current = fabric.use(mid, agent_id=agent_id, tenant_id=tenant_id, audit=False)
        if not current.usable:
            continue
        found[mid] = (historical, current)
    if len(found) != len(set(ids)):
        # Do not distinguish missing, private, withdrawn or erased IDs.
        raise Erased("requested evidence is unavailable")
    ref_items = []
    for mid in ids:
        historical, _current = found[mid]
        digest = digest_json({"id": mid, "version": historical.version,
                              "content": historical.content,
                              "seq": recorded[(mid, historical.version)][1]})
        ref_items.append(BeliefReference(mid, historical.version, tenant_id, digest))
    refs = tuple(ref_items)
    if decision is not None:
        if type(decision) is not DecisionRecord:
            raise CDMError("decision must be a typed original DecisionRecord")
        if (decision.sequence > context.known_at or decision.agent_id != agent_id
                or decision.tenant_id != tenant_id
                or not set(decision.evidence) <= set(refs)):
            raise CDMError("decision record is not bounded by this authorized capture")
        if not verify_decision_record(fabric, decision):
            raise CDMError("decision record has no matching immutable source event")
    body = {"schema": "memory-fabric-cdm-v1", "principal": agent_id, "tenant": tenant_id,
            "known_at": context.known_at, "valid_at": context.valid_at,
            "source_head": start_head,
            "evidence": [{"id": r.belief_id, "version": r.version, "digest": r.digest} for r in refs],
            "decision": asdict(decision) if decision is not None else None}
    try:
        still_verified = principal.principal()
        still_verified.require_permission(PERM_READ)
        if still_verified.agent_id != agent_id or still_verified.tenant_id != tenant_id:
            raise Unauthorized("capture authorization changed")
    except Exception as exc:
        raise Unauthorized("capture authorization is unavailable") from exc
    return CaptureResult("memory-fabric-cdm-v1", agent_id, tenant_id, context.known_at,
                         context.valid_at, start_head, refs, True,
                         digest_json(body), source_currently_admissible=True,
                         historical_snapshot_only=True, decision=decision)


def validate_replay_option(decision: DecisionRecord, option: str, *,
                           intervention: Intervention | None = None) -> str:
    """Reject post-decision option injection unless a policy swap is explicit."""
    if type(decision) is not DecisionRecord or not isinstance(option, str) or not option:
        raise CDMError("a typed decision and non-empty option are required")
    if option in decision.options:
        return option
    if (type(intervention) is Intervention and intervention.operation == "swap_policy"
            and intervention.policy_id and intervention.policy_id != decision.policy_id):
        return option
    raise CDMError("replay option was not present at the original decision")


def record_decision(fabric: Any, principal: Any, *, options: Iterable[str],
                    selected: str | None, evidence: Iterable[BeliefReference],
                    policy_id: str, policy_digest: str,
                    constraints: Iterable[str] = (),
                    rng_state: RNGSnapshot | None = None,
                    rng_applicability: str = "not_applicable_deterministic",
                    tool_observations: Iterable[ToolObservation] = ()) -> DecisionRecord:
    """Append a digest-only decision receipt under a currently verified session."""
    if type(principal) is not Session or principal.service._fabric is not fabric:
        raise Unauthorized("decision recording requires a fabric-bound session")
    try:
        identity = principal.principal()
        identity.require_permission(PERM_WRITE)
    except Exception as exc:
        raise Unauthorized("decision recording authorization is unavailable") from exc
    options_tuple = tuple(options)
    evidence_tuple = tuple(evidence)
    constraints_tuple = tuple(constraints)
    tool_tuple = tuple(tool_observations)
    if not evidence_tuple or any(type(ref) is not BeliefReference for ref in evidence_tuple):
        raise CDMError("decision evidence must contain typed references")
    if any(ref.tenant_id != identity.tenant_id for ref in evidence_tuple):
        raise Unauthorized("decision evidence is outside the session tenant")
    with fabric.lock, fabric.log.transaction():
        fabric.refresh()
        try:
            current_identity = principal.principal()
            current_identity.require_permission(PERM_WRITE)
        except Exception as exc:
            raise Unauthorized("decision recording authorization is unavailable") from exc
        if (current_identity.agent_id != identity.agent_id
                or current_identity.tenant_id != identity.tenant_id):
            raise Unauthorized("decision recording identity changed")
        for ref in evidence_tuple:
            current = fabric.use(ref.belief_id, agent_id=identity.agent_id,
                                 tenant_id=identity.tenant_id, audit=False)
            if not current.usable or current.memory.version != ref.version:
                raise Erased("decision evidence is unavailable")
        sequence = fabric.log.head_seq + 1
        event_id = new_ulid()
        record = DecisionRecord(sequence, identity.tenant_id, identity.agent_id,
            options_tuple, selected, evidence_tuple, policy_id, policy_digest,
            constraints=constraints_tuple, source_event_id=event_id,
            rng_applicability=rng_applicability, rng_state=rng_state,
            tool_observations=tool_tuple)
        payload = {"decision_digest": digest_json(asdict(record)),
                   "policy_id": policy_id, "policy_digest": policy_digest,
                   "record_schema": record.schema, "tenant_id": identity.tenant_id}
        event = ev.Event(ev.EventType.CDM_DECISION_RECORDED, fabric.now(), payload,
                         agent_id=identity.agent_id, event_id=event_id)
        stored = fabric._emit(event)[0]
        if stored.seq != sequence or stored.event_id != event_id:
            raise CDMError("decision receipt sequence changed during append")
    return record


def verify_decision_record(fabric: Any, decision: DecisionRecord) -> bool:
    """Match a typed record to its immutable append-only event receipt."""
    if type(decision) is not DecisionRecord or decision.source_event_id is None:
        return False
    if not fabric.log.chain.verify(fabric.log.read()).ok:
        return False
    event = next(fabric.log.read(since_seq=decision.sequence - 1, limit=1), None)
    return bool(event is not None and event.seq == decision.sequence
        and event.event_id == decision.source_event_id
        and event.type == ev.EventType.CDM_DECISION_RECORDED
        and event.agent_id == decision.agent_id
        and event.payload.get("tenant_id") == decision.tenant_id
        and event.payload.get("decision_digest") == digest_json(asdict(decision))
        and event.payload.get("policy_id") == decision.policy_id
        and event.payload.get("policy_digest") == decision.policy_digest
        and event.payload.get("record_schema") == decision.schema)


def capture_rng_state(generator: random.Random) -> RNGSnapshot:
    """Capture the complete stdlib RNG state, including MT internal position."""
    if type(generator) is not random.Random:
        raise CDMError("RNG capture supports only an exact stdlib Random instance")
    version, internal, gaussian_next = generator.getstate()
    if not isinstance(internal, tuple) or len(internal) < 2:
        raise CDMError("stdlib RNG returned an unsupported state layout")
    return RNGSnapshot("python.random.MT19937", version, tuple(internal),
                       gaussian_next, internal[-1])

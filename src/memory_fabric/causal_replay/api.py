"""Read-only, in-process CDM facade over the existing governed store."""

from __future__ import annotations

__stability__ = "experimental"

from typing import Any, Iterable
from dataclasses import asdict

from .. import dependence, influence
from .. import events as ev
from ..identity import PERM_READ
from ..service import Session
from .capture import capture
from .types import CDMError, Erased, ReplayContext, Unauthorized
from .scheduler import Candidate, select_priority


class CausalReplayAPI:
    """Bounded local operations. No network listener or mutation endpoint exists."""

    def __init__(self, fabric: Any, principal: Any) -> None:
        if type(principal) is not Session or principal.service._fabric is not fabric:
            raise ValueError("a fabric-bound verified session is required")
        self._fabric = fabric
        self._principal = principal

    def capture(self, evidence_ids: Iterable[str], *, known_at: int,
                valid_at: int | None = None, max_events: int = 10_000):
        return capture(self._fabric, self._principal, evidence_ids,
                       context=ReplayContext(known_at, valid_at, max_events=max_events))

    def dispatch(self, operation: str, request: dict[str, Any]) -> dict[str, Any]:
        """Bounded pure-Python request dispatcher; no server or mutation path."""
        if type(request) is not dict or operation not in {"capture", "correction_impact"}:
            raise CDMError("unsupported CDM request")
        if operation == "capture":
            if set(request) - {"evidence_ids", "known_at", "valid_at", "max_events"}:
                raise CDMError("unknown capture request field")
            ids = request.get("evidence_ids")
            if type(ids) is not list or len(ids) > 100 or any(type(item) is not str for item in ids):
                raise CDMError("evidence_ids must be a list of at most 100 strings")
            known_at = request.get("known_at")
            valid_at = request.get("valid_at")
            max_events = request.get("max_events", 10_000)
            if (type(known_at) is not int
                    or (valid_at is not None and type(valid_at) is not int)
                    or type(max_events) is not int):
                raise CDMError("capture sequence and budget fields must be integers")
            receipt = self.capture(ids, known_at=known_at,
                valid_at=valid_at, max_events=max_events)
            return asdict(receipt)
        if set(request) != {"memory_id"} or type(request.get("memory_id")) is not str:
            raise CDMError("correction_impact requires only memory_id")
        return self.correction_impact(request["memory_id"])

    def correction_impact(self, memory_id: str) -> dict[str, Any]:
        try:
            principal = self._principal.principal()
            principal.require_permission(PERM_READ)
        except Exception as exc:
            raise Unauthorized("correction review authorization is unavailable") from exc

        def visible(mid: str) -> bool:
            if mid not in self._fabric.state.memories or mid in self._fabric.state.erased:
                return False
            if self._fabric.state.memories[mid].tenant_id != principal.tenant_id:
                return False
            try:
                return bool(self._fabric.use(mid, agent_id=principal.agent_id,
                    tenant_id=principal.tenant_id, audit=False).usable)
            except Exception:
                return False

        if not visible(memory_id):
            raise Erased("requested evidence is unavailable")
        raw_impact = influence.impact(self._fabric, memory_id)
        reach = {memory_id, *(mid for mid in raw_impact["potentially_contaminated"]["memories"]
                              if visible(mid))}
        visible_agents = set()
        for agent_id in raw_impact["potentially_contaminated"]["agents"]:
            candidate_id = agent_id.removeprefix("agent:")
            try:
                if self._fabric.principals.principal(candidate_id).tenant_id == principal.tenant_id:
                    visible_agents.add(agent_id)
            except Exception:
                continue
        scoped_impact: dict[str, Any] = {"memory_id": memory_id,
            "potentially_contaminated": {"memories": sorted(reach - {memory_id}),
                "agents": sorted(visible_agents),
                "possible_paraphrases": sorted(mid for mid in raw_impact["potentially_contaminated"]["possible_paraphrases"]
                                                if visible(mid))},
            "actually_retrieved": [row for row in raw_impact["actually_retrieved"]
                                   if row["memory"] in reach and row["by"] in visible_agents],
            "confirmed_use": {"relied_on": [], "authorized": []}}
        for row in raw_impact["confirmed_use"]["relied_on"]:
            episode = self._fabric.state.episodes.get(row["episode"].removeprefix("episode:"))
            if row["memory"] in reach and episode is not None and episode.agent_id == principal.agent_id:
                scoped_impact["confirmed_use"]["relied_on"].append(row)
        own_actions = {f"action:{event.seq}" for event in self._fabric.log.read_types(
            [ev.EventType.ACTION_GATED, ev.EventType.ACTION_EXECUTED])
            if event.agent_id == principal.agent_id}
        for row in raw_impact["confirmed_use"]["authorized"]:
            if row["memory"] in reach and row["action"] in own_actions:
                scoped_impact["confirmed_use"]["authorized"].append(row)
        raw_dependence = dependence.decisions_depending_on(self._fabric, memory_id)
        scoped_dependence = {"memory_id": memory_id, "reach": sorted(reach),
            "depended": [row for row in raw_dependence["depended"] if row["agent_id"] == principal.agent_id],
            "would_stand": [row for row in raw_dependence["would_stand"] if row["agent_id"] == principal.agent_id],
            "exposed_only": [agent for agent in raw_dependence["exposed_only"]
                             if agent == f"agent:{principal.agent_id}"]}
        depended = list(scoped_dependence["depended"])
        reviewed = list(scoped_dependence["would_stand"])
        review_candidates = []
        for row in depended + reviewed:
            hit = tuple(str(mid) for mid in row.get("in_reach", ()))
            # Governance sufficiency is not a measured choice effect. Risk and
            # relevance remain neutral until a verified replay is available.
            review_candidates.append(Candidate(
                candidate_id=f"decision:{row['seq']}", sequence=int(row["seq"]),
                risk=1.0 if row in depended else 0.5,
                relevance=1.0 if row in depended else 0.5,
                uncertainty=1.0 if row in depended else 0.5,
                neighbors=hit))
        ranked = select_priority(review_candidates, k=len(review_candidates))
        ranked_rows = []
        by_id = {f"decision:{row['seq']}": row for row in depended + reviewed}
        for candidate in ranked:
            row = by_id[candidate.candidate_id]
            ranked_rows.append({"decision": row, "priority_score": round(
                0.5 * candidate.risk + 0.3 * candidate.relevance
                + 0.2 * candidate.uncertainty, 6),
                "reason": "recorded evidence sufficiency changed" if row in depended
                          else "recorded evidence sufficiency remains"})
        return {"influence": scoped_impact, "dependence": scoped_dependence,
            "review_candidates": ranked_rows,
            "review_only": True, "authority_changed": False,
            "interpretation": "priority ranks review workload from recorded evidence sufficiency; it is not a replayed choice effect or proof of causation"}

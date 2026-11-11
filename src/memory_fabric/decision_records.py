"""Typed, serializable records for decisions grounded in versioned evidence.

Decision records and typed, replayable decision-to-evidence/effect links.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
import hashlib
import json
import math
import threading
from types import MappingProxyType
from typing import Any, Mapping

from .events import Event, EventType
from .eventlog import EventLog

__stability__ = "beta"

class DecisionEdgeError(ValueError):
    """A decision edge is malformed or points outside its decision."""


@dataclass(frozen=True, slots=True)
class DecisionEdge:
    """A typed claim or tool-effect relationship recorded in the event log."""

    edge_id: str
    decision_id: str
    relation: str
    target_id: str
    actor_id: str
    recorded_at: str
    evidence: EvidenceVersion | None = None

    def __post_init__(self) -> None:
        if self.relation not in {"relied_on", "authorized", "executed"}:
            raise DecisionEdgeError("relation must be relied_on, authorized, or executed")
        for name in ("edge_id", "decision_id", "target_id", "actor_id"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                raise DecisionEdgeError(f"{name} must not be empty")
        _validate_timestamp(self.recorded_at, "recorded_at")
        if self.relation == "relied_on" and not isinstance(self.evidence, EvidenceVersion):
            raise DecisionEdgeError("relied_on edges require an exact evidence version")
        if self.relation != "relied_on" and self.evidence is not None:
            raise DecisionEdgeError("tool-effect edges cannot carry claim evidence")

    def to_dict(self) -> dict[str, Any]:
        return {"edge_id": self.edge_id, "decision_id": self.decision_id,
                "relation": self.relation, "target_id": self.target_id,
                "actor_id": self.actor_id, "recorded_at": self.recorded_at,
                "evidence": self.evidence.to_dict() if self.evidence else None}


@dataclass(frozen=True, slots=True)
class SeenExposure:
    """A recorded exposure observation; it does not assert that it was relied on."""

    decision_id: str
    exposure_event_id: str
    memory_id: str
    version: int
    actor_id: str
    recorded_at: str

    def __post_init__(self) -> None:
        if not all(isinstance(value, str) and value.strip() for value in
                   (self.decision_id, self.exposure_event_id, self.memory_id, self.actor_id)):
            raise DecisionEdgeError("seen exposure identities must not be empty")
        if not isinstance(self.version, int) or isinstance(self.version, bool) or self.version < 1:
            raise DecisionEdgeError("seen exposure version must be positive")
        _validate_timestamp(self.recorded_at, "recorded_at")


@dataclass(frozen=True, slots=True)
class DecisionGraph:
    decision: DecisionRecord
    seen: tuple[SeenExposure, ...]
    relied_on: tuple[DecisionEdge, ...]
    authorized: tuple[DecisionEdge, ...]
    executed: tuple[DecisionEdge, ...]


@dataclass(frozen=True, slots=True)
class DecisionImpact:
    """A correction/retraction impact with direct evidence and effect paths."""

    trigger_event_id: str
    changed_evidence: EvidenceVersion
    decision_id: str
    proof_edges: tuple[DecisionEdge, ...]
    affected_effects: tuple[DecisionEdge, ...]


@dataclass(frozen=True, slots=True)
class DecisionReevaluationReceipt:
    """Deterministic, advisory record that a changed premise affects a decision."""

    receipt_id: str
    trigger_event_id: str
    decision_id: str
    changed_premise: EvidenceVersion
    current_decision_status: str
    proof_edge_ids: tuple[str, ...]
    affected_effect_ids: tuple[str, ...]
    reevaluation_required: bool = True
    action_authorized: bool = False
    schema_version: int = 1

    def __post_init__(self) -> None:
        for name in ("receipt_id", "trigger_event_id", "decision_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must not be empty")
        if not isinstance(self.changed_premise, EvidenceVersion):
            raise TypeError("changed_premise must be an exact EvidenceVersion")
        if self.current_decision_status not in DECISION_STATUSES:
            raise ValueError("current_decision_status must use the DecisionRecord status vocabulary")
        proof_ids = tuple(self.proof_edge_ids)
        effect_ids = tuple(self.affected_effect_ids)
        if not proof_ids or any(not isinstance(item, str) or not item.strip()
                                for item in proof_ids):
            raise ValueError("proof_edge_ids must contain at least one non-empty edge ID")
        if len(proof_ids) != len(set(proof_ids)):
            raise ValueError("proof_edge_ids must be unique")
        if any(not isinstance(item, str) or not item.strip() for item in effect_ids):
            raise ValueError("affected_effect_ids must contain non-empty edge IDs")
        if len(effect_ids) != len(set(effect_ids)):
            raise ValueError("affected_effect_ids must be unique")
        if self.reevaluation_required is not True or self.action_authorized is not False:
            raise ValueError("reevaluation receipts are advisory and never grant action authority")
        if self.schema_version != 1:
            raise ValueError("unsupported DecisionReevaluationReceipt schema_version")
        object.__setattr__(self, "proof_edge_ids", proof_ids)
        object.__setattr__(self, "affected_effect_ids", effect_ids)

    def to_dict(self) -> dict[str, Any]:
        """Return the stable machine-readable receipt representation."""
        return {
            "schema_version": self.schema_version,
            "receipt_id": self.receipt_id,
            "trigger_event_id": self.trigger_event_id,
            "decision_id": self.decision_id,
            "changed_premise": self.changed_premise.to_dict(),
            "current_decision_status": self.current_decision_status,
            "proof_edge_ids": list(self.proof_edge_ids),
            "affected_effect_ids": list(self.affected_effect_ids),
            "reevaluation_required": self.reevaluation_required,
            "action_authorized": self.action_authorized,
        }

    def to_json(self) -> str:
        """Serialize canonically so the same replay yields byte-identical output."""
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False)


@dataclass(frozen=True, slots=True)
class DecisionAlternativeAssessment:
    """Why a non-selected option lost and which evidence made it lose."""

    decision_id: str
    option_id: str
    rejection_reason: str
    rejection_evidence: tuple[EvidenceVersion, ...]
    assessed_by: str
    assessed_at: str

    def __post_init__(self) -> None:
        for name in ("decision_id", "option_id", "assessed_by"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                raise DecisionEdgeError(f"{name} must not be empty")
        if not isinstance(self.rejection_reason, str) or not self.rejection_reason.strip():
            raise DecisionEdgeError("rejection_reason must not be empty")
        _validate_timestamp(self.assessed_at, "assessed_at")
        evidence = tuple(self.rejection_evidence)
        if not evidence or any(not isinstance(item, EvidenceVersion) for item in evidence):
            raise DecisionEdgeError("rejection_evidence must name exact evidence versions")
        if len(evidence) != len(set(evidence)):
            raise DecisionEdgeError("rejection_evidence versions must be unique")
        object.__setattr__(self, "rejection_evidence", evidence)

    def to_dict(self) -> dict[str, Any]:
        return {"decision_id": self.decision_id, "option_id": self.option_id,
                "rejection_reason": self.rejection_reason,
                "rejection_evidence": [item.to_dict() for item in self.rejection_evidence],
                "assessed_by": self.assessed_by, "assessed_at": self.assessed_at}


@dataclass(frozen=True, slots=True)
class DecisionAlternativeView:
    option_id: str
    description: str
    selected: bool
    rejection_reason: str | None
    rejection_evidence: tuple[EvidenceVersion, ...]
    reconsideration: str
    might_become_viable: bool


def _decode_edge(data: Mapping[str, Any]) -> DecisionEdge:
    evidence = data.get("evidence")
    return DecisionEdge(data["edge_id"], data["decision_id"], data["relation"],
                        data["target_id"], data["actor_id"], data["recorded_at"],
                        EvidenceVersion(evidence["memory_id"], evidence["version"])
                        if evidence is not None else None)


class DecisionLedger:
    """Append-only decision graph backed by the Memory Fabric event log."""

    def __init__(self, log: EventLog, clock: Any) -> None:
        self._log = log
        self._clock = clock
        self._index_lock = threading.RLock()
        self._indexed_seq = 0
        self._indexed_event_count = 0
        self._events_by_id: dict[str, Event] = {}
        self._decisions: dict[str, DecisionRecord] = {}
        self._edges_by_decision: dict[str, list[DecisionEdge]] = {}
        self._edges_by_evidence: dict[EvidenceVersion, list[DecisionEdge]] = {}
        self._versions_by_memory: dict[str, set[EvidenceVersion]] = {}
        self._seen_by_decision: dict[str, list[SeenExposure]] = {}
        self._exposures: dict[str, Event] = {}
        self._edge_ids: set[str] = set()
        self._assessments_by_decision: dict[str, dict[str, DecisionAlternativeAssessment]] = {}

    def _sync_index(self) -> None:
        with self._index_lock:
            self._sync_index_unlocked()

    def _sync_index_unlocked(self) -> None:
        """Apply only events after the index cursor; safe after external appends."""
        for event in self._log.read(since_seq=self._indexed_seq):
            self._indexed_event_count += 1
            if event.seq is not None:
                self._indexed_seq = event.seq
            self._events_by_id[event.event_id] = event
            if event.type == EventType.EXPOSURE_DECIDED:
                self._exposures[event.event_id] = event
            elif event.type == EventType.DECISION_RECORDED:
                decision = DecisionRecord.from_dict(event.payload["decision"])
                if decision.decision_id in self._decisions:
                    raise DecisionEdgeError("replayed decision_id already exists")
                self._decisions[decision.decision_id] = decision
            elif event.type == EventType.DECISION_STATUS_CHANGED:
                row = event.payload["transition"]
                decision_id = event.payload["decision_id"]
                status_decision = self._decisions.get(decision_id)
                if status_decision is None:
                    raise DecisionEdgeError("replayed status transition refers to an unknown decision")
                transition = DecisionStatusTransition(**row)
                if event.agent_id != transition.actor_id:
                    raise DecisionTransitionError("replayed status actor does not match event actor")
                if transition.from_status != status_decision.status:
                    raise DecisionTransitionError(
                        f"replayed status expected {transition.from_status}, current status is {status_decision.status}")
                self._decisions[decision_id] = status_decision.transition_status(
                    transition.to_status, changed_at=transition.changed_at,
                    actor_id=transition.actor_id)
            elif event.type == EventType.DECISION_EDGE_RECORDED:
                edge = _decode_edge(event.payload["edge"])
                edge_decision = self._decisions.get(edge.decision_id)
                if edge_decision is None:
                    raise DecisionEdgeError("replayed edge refers to an unknown decision")
                if edge.edge_id in self._edge_ids:
                    raise DecisionEdgeError("replayed edge_id already exists")
                if edge.relation == "relied_on":
                    if edge.evidence not in edge_decision.evidence_versions:
                        raise DecisionEdgeError(
                            "replayed reliance edge references evidence absent from its decision")
                    assert edge.evidence is not None
                    self._edges_by_evidence.setdefault(edge.evidence, []).append(edge)
                    self._versions_by_memory.setdefault(edge.evidence.memory_id, set()).add(
                        edge.evidence)
                self._edge_ids.add(edge.edge_id)
                self._edges_by_decision.setdefault(edge.decision_id, []).append(edge)
            elif event.type == EventType.DECISION_SEEN:
                row = event.payload
                seen_decision = self._decisions.get(row["decision_id"])
                source = self._exposures.get(row["exposure_event_id"])
                if seen_decision is None:
                    raise DecisionEdgeError("replayed seen event refers to an unknown decision")
                if (source is None or not source.payload.get("exposed")
                        or source.agent_id != seen_decision.agent_id
                        or source.payload.get("memory_id") != row["memory_id"]
                        or source.payload.get("version") != row["version"]):
                    raise DecisionEdgeError("replayed seen event does not match an exposed source")
                seen = SeenExposure(row["decision_id"], row["exposure_event_id"],
                                    row["memory_id"], row["version"],
                                    event.agent_id or "", row["recorded_at"])
                self._seen_by_decision.setdefault(seen.decision_id, []).append(seen)
            elif event.type == EventType.DECISION_OPTION_ASSESSED:
                row = event.payload["assessment"]
                assessment = DecisionAlternativeAssessment(
                    row["decision_id"], row["option_id"], row["rejection_reason"],
                    tuple(EvidenceVersion(item["memory_id"], item["version"])
                          for item in row["rejection_evidence"]),
                    row["assessed_by"], row["assessed_at"],
                )
                assessed_decision = self._decisions.get(assessment.decision_id)
                if assessed_decision is None:
                    raise DecisionEdgeError("replayed assessment refers to an unknown decision")
                option = next((item for item in assessed_decision.options
                               if item.option_id == assessment.option_id), None)
                if option is None or assessment.option_id == assessed_decision.chosen_option_id:
                    raise DecisionEdgeError("replayed assessment must describe a non-selected option")
                if not set(assessment.rejection_evidence).issubset(option.evidence):
                    raise DecisionEdgeError("replayed rejection evidence is absent from its option")
                assessments = self._assessments_by_decision.setdefault(
                    assessment.decision_id, {})
                if assessment.option_id in assessments:
                    raise DecisionEdgeError("replayed alternative assessment already exists")
                assessments[assessment.option_id] = assessment

    @property
    def index_stats(self) -> Mapping[str, int]:
        """Work counters for verifying incremental replay and index freshness."""
        self._sync_index()
        return MappingProxyType({"indexed_through_seq": self._indexed_seq,
                                 "events_scanned": self._indexed_event_count,
                                 "decisions": len(self._decisions),
                                 "reliance_edges": sum(len(edges)
                                                       for edges in self._edges_by_evidence.values())})

    def record(self, decision: DecisionRecord) -> None:
        if self.get(decision.decision_id) is not None:
            raise DecisionEdgeError("decision_id already exists")
        event = Event(type=EventType.DECISION_RECORDED, ts=self._clock(),
                      agent_id=decision.agent_id,
                      payload={"decision": decision.to_dict()},
                      event_id="decision_" + hashlib.sha256(
                          decision.decision_id.encode("utf-8")).hexdigest())
        try:
            self._log.append(event)
        except Exception as exc:
            if self.get(decision.decision_id) is not None:
                raise DecisionEdgeError("decision_id already exists") from exc
            raise

    def transition_decision(self, decision_id: str, status: str, *,
                            changed_at: str, actor_id: str) -> DecisionRecord:
        """Persist a legal status transition and replay it into the current record.

        The event-log write transaction serializes competing transitions across
        processes. A repeated identical call is idempotent; an illegal or stale
        transition appends nothing.
        """
        with self._log.transaction():
            self._sync_index()
            current = self._decisions.get(decision_id)
            if current is None:
                raise DecisionEdgeError("decision does not exist")
            if current.status_history:
                previous = current.status_history[-1]
                if (previous.to_status == status and previous.changed_at == changed_at
                        and previous.actor_id == actor_id):
                    return current
            updated = current.transition_status(status, changed_at=changed_at,
                                                actor_id=actor_id)
            transition = updated.status_history[-1]
            canonical = json.dumps(transition.to_dict(), sort_keys=True,
                                   separators=(",", ":"))
            event_id = "decision_status_" + hashlib.sha256(
                f"{decision_id}\0{canonical}".encode("utf-8")).hexdigest()
            self._log.append(Event(
                type=EventType.DECISION_STATUS_CHANGED, ts=self._clock(),
                agent_id=actor_id,
                payload={"decision_id": decision_id, "transition": transition.to_dict()},
                event_id=event_id,
            ))
        self._sync_index()
        result = self._decisions.get(decision_id)
        if result is None:
            raise DecisionEdgeError("decision disappeared during status replay")
        return result

    def get(self, decision_id: str) -> DecisionRecord | None:
        self._sync_index()
        return self._decisions.get(decision_id)

    def link(self, edge: DecisionEdge) -> None:
        decision = self.get(edge.decision_id)
        if decision is None:
            raise DecisionEdgeError("decision does not exist")
        if edge.relation == "relied_on" and edge.evidence not in decision.evidence_versions:
            raise DecisionEdgeError("relied_on evidence must be listed by the decision")
        existing = self.graph(edge.decision_id)
        if any(item.edge_id == edge.edge_id for group in
               (existing.relied_on, existing.authorized, existing.executed) for item in group):
            raise DecisionEdgeError("edge_id already exists")
        try:
            self._log.append(Event(type=EventType.DECISION_EDGE_RECORDED, ts=self._clock(),
                                   agent_id=edge.actor_id, payload={"edge": edge.to_dict()},
                                   event_id="decision_edge_" + hashlib.sha256(
                                       edge.edge_id.encode("utf-8")).hexdigest()))
        except Exception as exc:
            current = self.graph(edge.decision_id)
            if any(item.edge_id == edge.edge_id for group in
                   (current.relied_on, current.authorized, current.executed) for item in group):
                raise DecisionEdgeError("edge_id already exists") from exc
            raise

    def observe(self, decision_id: str, exposure_event_id: str, *, actor_id: str,
                recorded_at: str) -> None:
        decision = self.get(decision_id)
        if decision is None:
            raise DecisionEdgeError("decision does not exist")
        self._sync_index()
        source = self._exposures.get(exposure_event_id)
        if source is None or source.type != EventType.EXPOSURE_DECIDED:
            raise DecisionEdgeError("seen must reference an ExposureDecided event")
        if not source.payload.get("exposed"):
            raise DecisionEdgeError("withheld exposure cannot be marked seen")
        _validate_timestamp(recorded_at, "recorded_at")
        if source.agent_id != decision.agent_id:
            raise DecisionEdgeError("exposure actor must match the decision agent")
        if not isinstance(actor_id, str) or not actor_id.strip():
            raise DecisionEdgeError("actor_id must not be empty")
        event_id = "decision_seen_" + hashlib.sha256(
            f"{decision_id}\0{exposure_event_id}".encode("utf-8")).hexdigest()
        existing = next((seen for seen in self._seen_by_decision.get(decision_id, [])
                         if seen.exposure_event_id == exposure_event_id), None)
        if existing is not None:
            if existing.actor_id == actor_id and existing.recorded_at == recorded_at:
                return
            raise DecisionEdgeError("seen observation already exists with different details")
        self._log.append(Event(type=EventType.DECISION_SEEN, ts=self._clock(), agent_id=actor_id,
                               payload={"decision_id": decision_id,
                                        "exposure_event_id": exposure_event_id,
                                        "memory_id": source.payload["memory_id"],
                                        "version": source.payload["version"],
                                        "recorded_at": recorded_at}, event_id=event_id))

    def graph(self, decision_id: str) -> DecisionGraph:
        self._sync_index()
        decision = self._decisions.get(decision_id)
        if decision is None:
            raise DecisionEdgeError("decision does not exist")
        edges = self._edges_by_decision.get(decision_id, [])
        seen = self._seen_by_decision.get(decision_id, [])
        return DecisionGraph(decision, tuple(seen),
                             tuple(e for e in edges if e.relation == "relied_on"),
                             tuple(e for e in edges if e.relation == "authorized"),
                             tuple(e for e in edges if e.relation == "executed"))

    def impacts_for(self, changed: EvidenceVersion, *,
                    trigger_event_id: str = "") -> tuple[DecisionImpact, ...]:
        """Return only decisions that explicitly relied on this exact version."""
        self._sync_index()
        results: list[DecisionImpact] = []
        for decision_id in sorted({edge.decision_id
                                   for edge in self._edges_by_evidence.get(changed, [])}):
            edges = self._edges_by_decision[decision_id]
            proof = tuple(sorted((edge for edge in edges if edge.relation == "relied_on"
                                  and edge.evidence == changed), key=lambda edge: edge.edge_id))
            results.append(DecisionImpact(
                trigger_event_id, changed, decision_id, proof,
                tuple(sorted((edge for edge in edges if edge.relation in {"authorized", "executed"}),
                             key=lambda edge: (edge.relation, edge.edge_id))),
            ))
        return tuple(results)

    def reference_impacts_for(self, changed: EvidenceVersion, *,
                              trigger_event_id: str = "") -> tuple[DecisionImpact, ...]:
        """Full-scan reference implementation used to verify the incremental index."""
        decisions = {record.decision_id: record for event in
                     self._log.read_types([EventType.DECISION_RECORDED])
                     if (record := DecisionRecord.from_dict(event.payload["decision"]))}
        grouped: dict[str, list[DecisionEdge]] = {}
        all_edges: dict[str, list[DecisionEdge]] = {}
        for event in self._log.read_types([EventType.DECISION_EDGE_RECORDED]):
            edge = _decode_edge(event.payload["edge"])
            all_edges.setdefault(edge.decision_id, []).append(edge)
            if edge.relation == "relied_on" and edge.evidence == changed:
                grouped.setdefault(edge.decision_id, []).append(edge)
        return tuple(DecisionImpact(
            trigger_event_id, changed, decision_id,
            tuple(sorted(grouped[decision_id], key=lambda edge: edge.edge_id)),
            tuple(sorted((edge for edge in all_edges[decision_id]
                          if edge.relation in {"authorized", "executed"}),
                         key=lambda edge: (edge.relation, edge.edge_id))),
        ) for decision_id in sorted(grouped) if decision_id in decisions)

    def impacts_from_event(self, trigger_event_id: str) -> tuple[DecisionImpact, ...]:
        """Resolve a correction/retraction event into exact impacted decisions.

        A new memory version invalidates reliance on prior versions of that
        memory. Retraction events target their stated origin memory version.
        Other event kinds are rejected rather than guessed at.
        """
        self._sync_index()
        trigger = self._events_by_id.get(trigger_event_id)
        if trigger is None:
            raise DecisionEdgeError("trigger event does not exist")
        changed: set[EvidenceVersion] = set()
        if trigger.type == EventType.MEMORY_VERSIONED:
            memory = trigger.payload["memory"]
            memory_id, current_version = memory["id"], memory["version"]
            known = {evidence for evidence in self._versions_by_memory.get(memory_id, set())
                     if evidence.version < current_version}
            changed.update(known)
        elif trigger.type == EventType.RETRACTION_APPLIED:
            payload = trigger.payload
            changed.add(EvidenceVersion(payload["origin_memory_id"],
                                        payload["origin_memory_version"]))
            local_memory_id = payload.get("local_memory_id")
            if local_memory_id:
                changed.update(self._versions_by_memory.get(local_memory_id, set()))
        else:
            raise DecisionEdgeError("trigger must be MemoryVersioned or RetractionApplied")
        return tuple(impact for evidence in sorted(changed)
                     for impact in self.impacts_for(evidence, trigger_event_id=trigger_event_id))

    def reevaluation_receipts_from_event(
        self, trigger_event_id: str,
    ) -> tuple[DecisionReevaluationReceipt, ...]:
        """Build deterministic advisory receipts for each exact correction impact.

        Receipts are projections over the durable log: replaying the same log
        reproduces the same IDs and canonical JSON. They identify changed
        premises and affected effects but never authorize those effects.
        """
        receipts: list[DecisionReevaluationReceipt] = []
        for impact in self.impacts_from_event(trigger_event_id):
            decision = self._decisions.get(impact.decision_id)
            if decision is None:
                raise DecisionEdgeError("impacted decision disappeared during receipt construction")
            data: dict[str, Any] = {
                "schema_version": 1,
                "trigger_event_id": impact.trigger_event_id,
                "decision_id": impact.decision_id,
                "changed_premise": impact.changed_evidence.to_dict(),
                "current_decision_status": decision.status,
                "proof_edge_ids": [edge.edge_id for edge in impact.proof_edges],
                "affected_effect_ids": [edge.edge_id for edge in impact.affected_effects],
                "reevaluation_required": True,
                "action_authorized": False,
            }
            canonical = json.dumps(data, sort_keys=True, separators=(",", ":"),
                                   ensure_ascii=False)
            receipt_id = "reevaluation_" + hashlib.sha256(
                canonical.encode("utf-8")).hexdigest()
            receipts.append(DecisionReevaluationReceipt(
                receipt_id=receipt_id,
                trigger_event_id=impact.trigger_event_id,
                decision_id=impact.decision_id,
                changed_premise=impact.changed_evidence,
                current_decision_status=decision.status,
                proof_edge_ids=tuple(edge.edge_id for edge in impact.proof_edges),
                affected_effect_ids=tuple(edge.edge_id for edge in impact.affected_effects),
            ))
        return tuple(receipts)

    def assess_alternative(self, assessment: DecisionAlternativeAssessment) -> None:
        """Append why a non-selected option lost, tied to exact blocking evidence."""
        self._sync_index()
        decision = self._decisions.get(assessment.decision_id)
        if decision is None:
            raise DecisionEdgeError("decision does not exist")
        option = next((item for item in decision.options
                       if item.option_id == assessment.option_id), None)
        if option is None or assessment.option_id == decision.chosen_option_id:
            raise DecisionEdgeError("assessment must describe a registered non-selected option")
        if not set(assessment.rejection_evidence).issubset(option.evidence):
            raise DecisionEdgeError("rejection evidence must be listed by the alternative")
        if assessment.option_id in self._assessments_by_decision.get(assessment.decision_id, {}):
            raise DecisionEdgeError("alternative assessment already exists")
        event_id = "decision_assessment_" + hashlib.sha256(
            f"{assessment.decision_id}\0{assessment.option_id}".encode("utf-8")).hexdigest()
        self._log.append(Event(type=EventType.DECISION_OPTION_ASSESSED,
                               ts=self._clock(), agent_id=assessment.assessed_by,
                               payload={"assessment": assessment.to_dict()},
                               event_id=event_id))

    def reassess_alternatives(self, decision_id: str,
                              corrected: EvidenceVersion) -> tuple[DecisionAlternativeView, ...]:
        """Explain every option and flag only those whose rejection basis changed."""
        self._sync_index()
        decision = self._decisions.get(decision_id)
        if decision is None:
            raise DecisionEdgeError("decision does not exist")
        assessments = self._assessments_by_decision.get(decision_id, {})
        result: list[DecisionAlternativeView] = []
        for option in decision.options:
            if option.option_id == decision.chosen_option_id:
                result.append(DecisionAlternativeView(
                    option.option_id, option.description, True, None, option.evidence,
                    "selected", False))
                continue
            assessment = assessments.get(option.option_id)
            if assessment is None:
                result.append(DecisionAlternativeView(
                    option.option_id, option.description, False, None, option.evidence,
                    "unassessed", False))
                continue
            reconsider = corrected in assessment.rejection_evidence
            result.append(DecisionAlternativeView(
                option.option_id, option.description, False, assessment.rejection_reason,
                assessment.rejection_evidence,
                "reconsider" if reconsider else "still_rejected", reconsider))
        return tuple(result)

DECISION_STATUSES = frozenset({"proposed", "approved", "executed", "superseded",
                               "requires_reconsideration"})
_SCALAR_TYPES = (str, int, float, bool, type(None))
_STATUS_TRANSITIONS = {
    "proposed": frozenset({"approved", "superseded", "requires_reconsideration"}),
    "approved": frozenset({"executed", "superseded", "requires_reconsideration"}),
    "executed": frozenset({"superseded", "requires_reconsideration"}),
    "requires_reconsideration": frozenset({"proposed", "approved", "superseded"}),
    "superseded": frozenset(),
}


class DecisionTransitionError(ValueError):
    """A requested status change violates the append-only decision lifecycle."""

    code = "illegal_status_transition"


def _validate_timestamp(value: str, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be a non-empty ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must include a timezone offset")


@dataclass(frozen=True, slots=True)
class DecisionStatusTransition:
    from_status: str
    to_status: str
    changed_at: str
    actor_id: str

    def __post_init__(self) -> None:
        if self.from_status not in DECISION_STATUSES or self.to_status not in DECISION_STATUSES:
            raise ValueError("transition statuses must use the DecisionRecord status vocabulary")
        if self.to_status not in _STATUS_TRANSITIONS[self.from_status]:
            raise DecisionTransitionError(f"illegal decision status transition: {self.from_status} -> {self.to_status}")
        _validate_timestamp(self.changed_at, "changed_at")
        if not isinstance(self.actor_id, str) or not self.actor_id.strip():
            raise ValueError("transition actor_id must not be empty")

    def to_dict(self) -> dict[str, str]:
        return {"from_status": self.from_status, "to_status": self.to_status,
                "changed_at": self.changed_at, "actor_id": self.actor_id}


@dataclass(frozen=True, slots=True, order=True)
class EvidenceVersion:
    """An exact memory version referenced by a decision or alternative."""

    memory_id: str
    version: int

    def __post_init__(self) -> None:
        if not isinstance(self.memory_id, str) or not self.memory_id.strip():
            raise ValueError("evidence memory_id must not be empty")
        if not isinstance(self.version, int) or isinstance(self.version, bool) or self.version < 1:
            raise ValueError("evidence version must be a positive integer")

    def to_dict(self) -> dict[str, Any]:
        return {"memory_id": self.memory_id, "version": self.version}


@dataclass(frozen=True, slots=True)
class DecisionOption:
    """A named candidate choice and the exact evidence versions supporting it."""

    option_id: str
    description: str
    evidence: tuple[EvidenceVersion, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.option_id, str) or not self.option_id.strip():
            raise ValueError("option_id must not be empty")
        if not isinstance(self.description, str) or not self.description.strip():
            raise ValueError("option description must not be empty")
        normalized = tuple(self.evidence)
        if any(not isinstance(item, EvidenceVersion) for item in normalized):
            raise TypeError("option evidence must contain EvidenceVersion values")
        if len(normalized) != len(set(normalized)):
            raise ValueError("option evidence versions must be unique")
        object.__setattr__(self, "evidence", normalized)

    def to_dict(self) -> dict[str, Any]:
        return {"option_id": self.option_id, "description": self.description,
                "evidence": [item.to_dict() for item in self.evidence]}


@dataclass(frozen=True, slots=True)
class DecisionRecord:
    """A decision's goal, options, chosen option, evidence, and constraints."""

    decision_id: str
    tenant_id: str
    agent_id: str
    decided_at: str
    goal: str
    options: tuple[DecisionOption, ...]
    chosen_option_id: str | None
    evidence_versions: tuple[EvidenceVersion, ...]
    constraints: Mapping[str, str | int | float | bool | None]
    status: str = "proposed"
    status_history: tuple[DecisionStatusTransition, ...] = ()
    schema_version: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.decision_id, str) or not self.decision_id.strip():
            raise ValueError("decision_id must not be empty")
        if not isinstance(self.tenant_id, str) or not self.tenant_id.strip():
            raise ValueError("tenant_id must not be empty")
        if not isinstance(self.agent_id, str) or not self.agent_id.strip():
            raise ValueError("agent_id must not be empty")
        _validate_timestamp(self.decided_at, "decided_at")
        if not isinstance(self.goal, str) or not self.goal.strip():
            raise ValueError("goal must not be empty")
        if not isinstance(self.schema_version, int) or isinstance(self.schema_version, bool) \
                or self.schema_version != 1:
            raise ValueError("unsupported DecisionRecord schema_version")
        if not isinstance(self.status, str) or self.status not in DECISION_STATUSES:
            raise ValueError(f"status must be one of {sorted(DECISION_STATUSES)}")
        options = tuple(self.options)
        if not options or any(not isinstance(option, DecisionOption) for option in options):
            raise ValueError("at least one DecisionOption is required")
        ids = [option.option_id for option in options]
        if len(ids) != len(set(ids)):
            raise ValueError("option_id values must be unique")
        if self.chosen_option_id is not None and self.chosen_option_id not in ids:
            raise ValueError("chosen_option_id must identify a registered option")
        if self.status != "proposed" and self.chosen_option_id is None:
            raise ValueError(f"status {self.status!r} requires a chosen_option_id")
        history = tuple(self.status_history)
        current = "proposed"
        for transition in history:
            if not isinstance(transition, DecisionStatusTransition):
                raise TypeError("status_history must contain DecisionStatusTransition values")
            if transition.from_status != current:
                raise ValueError("status_history must be contiguous and append-only")
            current = transition.to_status
        if history and current != self.status:
            raise ValueError("status must match the final status_history entry")
        if not history and self.status != "proposed":
            raise ValueError("non-proposed status requires append-only status_history")
        evidence = tuple(self.evidence_versions)
        if any(not isinstance(item, EvidenceVersion) for item in evidence):
            raise TypeError("evidence_versions must contain EvidenceVersion values")
        if len(evidence) != len(set(evidence)):
            raise ValueError("evidence_versions must be unique")
        if not isinstance(self.constraints, Mapping):
            raise TypeError("constraints must be a mapping")
        constraints = dict(self.constraints)
        if any(not isinstance(key, str) or not key.strip() for key in constraints):
            raise ValueError("constraint names must be non-empty strings")
        if any(isinstance(value, (list, dict, set)) or not isinstance(value, _SCALAR_TYPES)
               for value in constraints.values()):
            raise TypeError("constraints must contain JSON scalar values")
        if any(isinstance(value, float) and not math.isfinite(value)
               for value in constraints.values()):
            raise ValueError("constraint floats must be finite JSON numbers")
        object.__setattr__(self, "options", options)
        object.__setattr__(self, "evidence_versions", evidence)
        object.__setattr__(self, "status_history", history)
        object.__setattr__(self, "constraints", MappingProxyType(dict(sorted(constraints.items()))))

    def transition_status(self, status: str, *, changed_at: str, actor_id: str) -> "DecisionRecord":
        """Return a new record with an appended, validated lifecycle transition."""
        transition = DecisionStatusTransition(self.status, status, changed_at, actor_id)
        return replace(self, status=status, status_history=self.status_history + (transition,))

    def to_dict(self) -> dict[str, Any]:
        """Return canonical JSON-compatible data with stable field ordering."""
        return {
            "schema_version": self.schema_version,
            "decision_id": self.decision_id,
            "tenant_id": self.tenant_id,
            "agent_id": self.agent_id,
            "decided_at": self.decided_at,
            "goal": self.goal,
            "options": [option.to_dict() for option in self.options],
            "chosen_option_id": self.chosen_option_id,
            "evidence_versions": [item.to_dict() for item in self.evidence_versions],
            "constraints": dict(self.constraints),
            "status": self.status,
            "status_history": [transition.to_dict() for transition in self.status_history],
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "DecisionRecord":
        """Parse the v1 wire representation, rejecting unknown/missing fields."""
        expected = {"schema_version", "decision_id", "tenant_id", "agent_id", "decided_at",
                    "goal", "options", "chosen_option_id", "evidence_versions", "constraints",
                    "status", "status_history"}
        if set(value) != expected:
            raise ValueError("DecisionRecord fields do not match schema version 1")
        try:
            if not isinstance(value["options"], list) or not isinstance(value["evidence_versions"], list):
                raise ValueError("options and evidence_versions must be arrays")
            for row in value["options"]:
                if not isinstance(row, Mapping) or set(row) != {"option_id", "description", "evidence"}:
                    raise ValueError("option fields do not match schema version 1")
                if not isinstance(row["evidence"], list):
                    raise ValueError("option evidence must be an array")
                if any(not isinstance(item, Mapping) or set(item) != {"memory_id", "version"}
                       for item in row["evidence"]):
                    raise ValueError("option evidence fields do not match schema version 1")
            if any(not isinstance(item, Mapping) or set(item) != {"memory_id", "version"}
                   for item in value["evidence_versions"]):
                raise ValueError("evidence version fields do not match schema version 1")
            if not isinstance(value["status_history"], list):
                raise ValueError("status_history must be an array")
            if any(not isinstance(item, Mapping)
                   or set(item) != {"from_status", "to_status", "changed_at", "actor_id"}
                   for item in value["status_history"]):
                raise ValueError("status transition fields do not match schema version 1")
            history = tuple(DecisionStatusTransition(**item) for item in value["status_history"])
            options = tuple(DecisionOption(
                option_id=row["option_id"], description=row["description"],
                evidence=tuple(EvidenceVersion(item["memory_id"], item["version"])
                               for item in row["evidence"]))
                for row in value["options"])
            refs = tuple(EvidenceVersion(item["memory_id"], item["version"])
                         for item in value["evidence_versions"])
            return cls(decision_id=value["decision_id"], tenant_id=value["tenant_id"],
                       agent_id=value["agent_id"], decided_at=value["decided_at"], goal=value["goal"],
                       options=options,
                       chosen_option_id=(value["chosen_option_id"]
                                         if value["chosen_option_id"] is not None else None),
                       evidence_versions=refs, constraints=value["constraints"],
                       status=value["status"], status_history=history,
                       schema_version=value["schema_version"])
        except (KeyError, TypeError) as exc:
            raise ValueError("malformed DecisionRecord v1 payload") from exc

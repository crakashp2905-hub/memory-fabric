"""A typed candidate graph: evidence dependency and causal claims kept apart (VEGA S04).

Nodes are observations, claims, beliefs, decisions, actions, outcomes and
explicit latent placeholders; each keeps its source, version and time identity.
Edges have closed types:

* ``REPORTS``, ``SUPPORTS``, ``CONTRADICTS`` - textual relations (a model may propose them);
* ``EXPOSED_TO``, ``RELIED_ON``, ``PRECEDES`` - observed dependence, from the provenance
  log only (:func:`add_dependence`); a model cannot add them;
* ``HYPOTHESIZED_CAUSE`` - a model's candidate, never more than a hypothesis;
* ``VERIFIED_COUNTERFACTUAL_EFFECT`` - only from an accepted replay verification
  (:func:`add_verified_effect`), with the certificate digest.

Every edge cites evidence references and a provenance digest (VEGA-CDM-044).
Causal edges must form a DAG; association edges may cycle (045). An edge from
evidence known after the decision it explains is refused (046). A declared
latent confounder between a cause and its effect makes the effect
``CAUSAL_UNIDENTIFIABLE`` (047). Revisions invalidate edges that cite obsolete
versions (049). :meth:`CandidateGraph.view` returns only what a principal may
see, and the same shape whether nothing exists or nothing is visible (050).
"""

from __future__ import annotations

__stability__ = "experimental"

import hashlib
import json
from dataclasses import dataclass, field
from typing import Iterable, Mapping

NODE_KINDS = ("observation", "claim", "belief", "decision", "action", "outcome", "latent")
TEXTUAL = frozenset({"REPORTS", "SUPPORTS", "CONTRADICTS"})
DEPENDENCE = frozenset({"EXPOSED_TO", "RELIED_ON", "PRECEDES"})
CAUSAL = frozenset({"HYPOTHESIZED_CAUSE", "VERIFIED_COUNTERFACTUAL_EFFECT"})
EDGE_TYPES = TEXTUAL | DEPENDENCE | CAUSAL
TIER_OF = {**{t: "TEXTUAL_RELEVANCE" for t in TEXTUAL},
           **{t: "OBSERVED_DEPENDENCE" for t in DEPENDENCE},
           "HYPOTHESIZED_CAUSE": "HYPOTHETICAL_EFFECT",
           "VERIFIED_COUNTERFACTUAL_EFFECT": "VALIDATED_COUNTERFACTUAL"}
MODEL_EDGE_TYPES = TEXTUAL | {"HYPOTHESIZED_CAUSE"}


class GraphError(ValueError):
    pass


@dataclass(frozen=True)
class Node:
    node_id: str
    kind: str
    tenant_id: str
    source: str
    version: int
    known_at: int
    valid_at: int | None = None

    def __post_init__(self) -> None:
        if self.kind not in NODE_KINDS:
            raise GraphError(f"unknown node kind {self.kind!r}")
        if not self.node_id or not self.tenant_id or type(self.version) is not int or self.version < 0:
            raise GraphError("node needs an id, a tenant and a version")
        if type(self.known_at) is not int:
            raise GraphError("node needs a recorded time")


@dataclass(frozen=True)
class Edge:
    source: str
    target: str
    kind: str
    evidence_refs: tuple[str, ...]
    provenance_digest: str
    origin: str  # provenance_log | advisor | verifier
    tier: str = ""
    certificate: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in EDGE_TYPES:
            raise GraphError(f"unknown edge type {self.kind!r}")
        if not self.evidence_refs or any("@" not in r for r in self.evidence_refs):
            raise GraphError("an edge cites version-specific evidence references")
        if len(self.provenance_digest) != 64:
            raise GraphError("an edge carries a provenance digest")
        if self.origin == "advisor" and self.kind not in MODEL_EDGE_TYPES:
            raise GraphError(f"a model cannot propose a {self.kind} edge")
        if self.kind in DEPENDENCE and self.origin != "provenance_log":
            raise GraphError("dependence edges come only from the provenance log")
        if self.kind == "VERIFIED_COUNTERFACTUAL_EFFECT" and (self.origin != "verifier"
                                                             or not self.certificate):
            raise GraphError("a verified effect needs the verifier and a certificate")
        object.__setattr__(self, "tier", TIER_OF[self.kind])


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


@dataclass
class CandidateGraph:
    tenant_id: str
    nodes: dict[str, Node] = field(default_factory=dict)
    edges: list[Edge] = field(default_factory=list)
    latent_between: set[tuple[str, str]] = field(default_factory=set)

    def add_node(self, node: Node) -> Node:
        if node.tenant_id != self.tenant_id:
            raise GraphError("a graph holds one tenant's nodes")
        if node.node_id in self.nodes and self.nodes[node.node_id] != node:
            raise GraphError(f"node {node.node_id} already exists with another identity")
        self.nodes[node.node_id] = node
        return node

    def _check_endpoints(self, edge: Edge) -> None:
        for end in (edge.source, edge.target):
            if end not in self.nodes:
                raise GraphError(f"edge endpoint {end} is not a node")
        if edge.kind in CAUSAL | {"SUPPORTS", "CONTRADICTS", "REPORTS"}:
            src, dst = self.nodes[edge.source], self.nodes[edge.target]
            if dst.kind in ("decision", "action") and src.known_at > dst.known_at:
                raise GraphError("evidence recorded after a decision cannot explain it")
        if edge.kind in CAUSAL and self._reaches(edge.target, edge.source):
            raise GraphError("causal edges must stay acyclic")

    def _reaches(self, start: str, goal: str) -> bool:
        stack, seen = [start], set()
        while stack:
            here = stack.pop()
            if here == goal:
                return True
            if here in seen:
                continue
            seen.add(here)
            stack.extend(e.target for e in self.edges if e.source == here and e.kind in CAUSAL)
        return False

    def add_edge(self, edge: Edge) -> Edge:
        self._check_endpoints(edge)
        self.edges.append(edge)
        return edge

    def propose(self, source: str, target: str, kind: str, evidence_refs: Iterable[str],
                receipt_digest: str) -> Edge:
        """An advisor's edge: textual or a hypothesis, never dependence or a verified effect."""
        refs = tuple(sorted(evidence_refs))
        return self.add_edge(Edge(source, target, kind, refs,
                                  digest({"refs": refs, "receipt": receipt_digest}), "advisor"))

    def add_dependence(self, source: str, target: str, kind: str, evidence_refs: Iterable[str],
                       log_digest: str) -> Edge:
        refs = tuple(sorted(evidence_refs))
        return self.add_edge(Edge(source, target, kind, refs, log_digest, "provenance_log"))

    def add_verified_effect(self, source: str, target: str, evidence_refs: Iterable[str],
                            verification: Mapping[str, object]) -> Edge:
        """Only an accepted verification with a certificate makes an effect verified (VEGA-CDM-043)."""
        if verification.get("accepted") is not True or not verification.get("certificate"):
            raise GraphError("no accepted verification: the edge stays a hypothesis")
        refs = tuple(sorted(evidence_refs))
        return self.add_edge(Edge(source, target, "VERIFIED_COUNTERFACTUAL_EFFECT", refs,
                                  digest(dict(verification)), "verifier",
                                  certificate=str(verification["certificate"])))

    def declare_latent(self, cause: str, effect: str, name: str) -> Node:
        """An unobserved common cause of ``cause`` and ``effect`` (VEGA-CDM-047)."""
        known = min(self.nodes[cause].known_at, self.nodes[effect].known_at)
        node = self.add_node(Node(f"latent:{name}", "latent", self.tenant_id, "declared", 0, known))
        self.latent_between.add((cause, effect))
        return node

    def identifiability(self, cause: str, effect: str) -> str:
        if (cause, effect) in self.latent_between:
            return "CAUSAL_UNIDENTIFIABLE"
        verified = any(e.kind == "VERIFIED_COUNTERFACTUAL_EFFECT" and e.source == cause
                       and e.target == effect for e in self.edges)
        return "SIMULATOR_IDENTIFIED" if verified else "NOT_ESTABLISHED"

    def invalidate(self, evidence_id: str, current_version: int | None) -> int:
        """Drop edges citing an obsolete or erased version of ``evidence_id`` (VEGA-CDM-049)."""
        def stale(ref: str) -> bool:
            eid, _, version = ref.rpartition("@")
            return eid == evidence_id and (current_version is None or int(version) != current_version)

        before = len(self.edges)
        self.edges = [e for e in self.edges if not any(stale(r) for r in e.evidence_refs)]
        if current_version is None:
            self.nodes = {k: n for k, n in self.nodes.items() if n.source != evidence_id}
            self.edges = [e for e in self.edges if e.source in self.nodes and e.target in self.nodes]
        return before - len(self.edges)

    def view(self, readable_refs: set[str], tenant_id: str) -> dict[str, object]:
        """Edges a principal may see. A foreign tenant gets the same empty shape as an empty graph."""
        if tenant_id != self.tenant_id:
            return {"edges": [], "nodes": 0}
        edges = [e for e in self.edges if set(e.evidence_refs) <= readable_refs]
        ends = {e.source for e in edges} | {e.target for e in edges}
        return {"edges": [{"source": e.source, "target": e.target, "kind": e.kind, "tier": e.tier,
                           "evidence_refs": list(e.evidence_refs)} for e in edges],
                "nodes": len(ends)}

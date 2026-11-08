"""Session compaction: one governed summary of what a session learned, for later sessions.

A long session leaves many memories. A later session with a context budget
cannot read them all, and forty near-duplicate turns compete badly in
retrieval. `compact_session` writes **one summary memory** for an episode.
It is built so that the summary cannot become a way around the store's
guarantees:

1. **It is a derivation, never a replacement.** The summary is written with
   `derive(method=consolidated)`, with every input as a versioned parent.
   Lineage, retraction and the influence graph follow it. A correction to
   any input contests the summary, and the summary inherits the lowest
   origin-bound authority among its inputs (`authority.py`), so a trusted
   summariser never launders an untrusted source.
2. **The originals stay.** Nothing is deleted or deprecated here, and
   retention does not retire a premise of an exposable memory
   (`MemoryFabric.sweep_retention`).
3. **Contradictions are kept, not resolved.** Inputs that give different
   values for one claim are written into the summary as a dispute, with
   every value and its source.
4. **Values are checked.** Every value stated by a usable input must appear
   in the summary, or the summary is refused (`CompactionRefused`). A
   summariser that drops a number cannot silently lose a fact.
5. **It passes the ingest screen** like any other write: an injection
   rewritten as an instruction is quarantined.

Inputs are the memories the session wrote (`source_episodes`) and the ones
it cited. Withdrawn and contested inputs are left out and listed in the
report; a summary is about what the session can still stand on.

The default summariser is extractive and deterministic. A model can be
passed as `summarise`, and its output goes through the same checks.
"""

from __future__ import annotations

__stability__ = "experimental"

from dataclasses import dataclass, field
import hashlib
import json
from typing import TYPE_CHECKING, Callable, Sequence

from .conflicts import author, claim, find_conflicts
from .events import EventType
from .model import EXPOSABLE_STATES, ProvenanceMethod, Scope, visible_to
from .identity import DEFAULT_TENANT
from .summary_dependencies import (
    DependencyMapRefused,
    make_edge_certificate,
    reconstruct_dependency_map,
    verify_stored_dependency_map,
)

if TYPE_CHECKING:  # pragma: no cover
    from .fabric import MemoryFabric
    from .model import Memory


class CompactionRefused(Exception):
    """The summary would lose or hide something; nothing was written."""


@dataclass
class CompactionReport:
    episode_id: str
    summary_id: str | None
    inputs: list[str] = field(default_factory=list)
    left_out: dict[str, str] = field(default_factory=dict)
    disputes: list[list[str]] = field(default_factory=list)


@dataclass
class HierarchicalCompactionReport:
    episode_id: str
    root_summary_id: str
    leaf_summary_ids: list[str]
    leaf_source_groups: list[list[str]]
    certificates: dict[str, str]


def session_memories(fabric: "MemoryFabric", episode_id: str) -> list["Memory"]:
    """What the session wrote, and what it cited, in log order."""
    ids: list[str] = [m.id for m in fabric.state.memories.values()
                      if episode_id in m.provenance.source_episodes]
    for event in fabric.log.read_types([EventType.MEMORY_CITED]):
        if event.episode_id == episode_id:
            mid = str(event.payload.get("memory_id"))
            if mid not in ids and mid in fabric.state.memories:
                ids.append(mid)
    return [fabric.state.memories[i] for i in ids]


def session_label(fabric: "MemoryFabric", episode_id: str) -> str:
    """The episode's task id, which names the session in its summary."""
    for event in fabric.log.read_types([EventType.EPISODE_STARTED]):
        if event.episode_id == episode_id:
            return str(event.payload.get("task_id") or episode_id)
    return episode_id


def extractive(memories: Sequence["Memory"], disputes: Sequence[Sequence["Memory"]]) -> str:
    """One line per distinct claim; disputed claims listed with every value and source.

    A claim is its identifiers and values (`conflicts.claim`): restatements of
    one claim keep only the shortest wording. A note with neither identifiers
    nor values ("shift handover went smoothly") is chatter and is dropped. The
    C1 pilot found the first version, which kept every distinct sentence, wrote
    summaries too long for any context budget.
    """
    disputed = {m.id for group in disputes for m in group}
    best: dict[object, str] = {}
    order: list[object] = []
    for memory in memories:
        if memory.id in disputed:
            continue
        ids, _, values = claim(memory.content)
        text = memory.content.strip()
        if not ids and not values:
            continue
        key = (ids, values) if (ids or values) else text.lower()
        if key not in best:
            order.append(key)
            best[key] = text
        elif len(text) < len(best[key]):
            best[key] = text
    lines = [best[k] for k in order]
    for group in disputes:
        lines.append("Disputed, unresolved: " + "; ".join(
            f"{m.content.strip()} (from {author(m)})" for m in group))
    return " ".join(lines)


def compact_session(fabric: "MemoryFabric", episode_id: str, agent_id: str,
                    summarise: Callable[[Sequence["Memory"], Sequence[Sequence["Memory"]]], str]
                    | None = None, scope: str | None = None,
                    tenant_id: str = DEFAULT_TENANT) -> CompactionReport:
    """Write one governed summary of an episode. Returns what was used and left out."""
    report = CompactionReport(episode_id=episode_id, summary_id=None)
    usable = []
    from .navigation import _visible

    if not agent_id or not tenant_id:
        raise CompactionRefused("compaction requires agent and tenant identities")
    with fabric._transaction():
        eligible = set(_visible(fabric, agent_id, tenant_id)) - fabric.state.erased
        for memory in session_memories(fabric, episode_id):
            if memory.tenant_id != tenant_id or not visible_to(memory, agent_id, fabric.state):
                continue   # no hidden IDs or counts in the report
            if memory.id in eligible:
                usable.append(memory)
            elif memory.lifecycle_state not in EXPOSABLE_STATES:
                report.left_out[memory.id] = memory.lifecycle_state.value
    if not usable:
        raise CompactionRefused(f"episode {episode_id} has no usable memories to compact")
    disputes = find_conflicts(usable)
    report.disputes = [[m.id for m in g] for g in disputes]
    # Named by its session, so "what did shift 3 establish?" can find it;
    # the facts themselves name no session.
    text = f"Session summary ({session_label(fabric, episode_id)}): " +         (summarise or extractive)(usable, disputes)
    _, _, stated = claim(text)
    missing = sorted({v for m in usable for v in claim(m.content)[2]} - set(stated))
    if missing:
        raise CompactionRefused(f"the summary drops values the session recorded: {missing}")
    for group in disputes:
        for m in group:
            if not set(claim(m.content)[2]) <= set(stated):
                raise CompactionRefused("the summary resolves a dispute instead of keeping it")
    dependency_error = None
    try:
        dependencies = reconstruct_dependency_map(text, usable)
    except DependencyMapRefused as exc:
        dependencies = None
        dependency_error = str(exc)
    narrowest = min((m.scope for m in usable), key=lambda s: s.rank)
    if scope is not None and Scope(scope).rank > narrowest.rank:
        raise CompactionRefused("a summary cannot widen its sources' visibility")
    with fabric._transaction():
        eligible = set(_visible(fabric, agent_id, tenant_id)) - fabric.state.erased
        if any(m.id not in eligible or fabric.state.memories[m.id].version != m.version for m in usable):
            raise CompactionRefused("compaction sources changed during summarization; retry with current evidence")
        summary_id = fabric.derive(
            agent_id, text, parents=[m.id for m in usable],
            method=ProvenanceMethod.CONSOLIDATED,
            context={
                "kind": "derived_claim",
                "compaction_of": episode_id,
                **(
                    {"summary_dependencies": dependencies}
                    if dependencies is not None
                    else {"summary_dependency_error": "unverified_fact_mapping"}
                ),
            },
            scope=scope or narrowest)
        report.summary_id = summary_id
        if dependencies is None and fabric.state.memories[summary_id].lifecycle_state in EXPOSABLE_STATES:
            raise CompactionRefused(
                f"summary dependency map could not be proven: {dependency_error}"
            )
    report.inputs = [m.id for m in usable]
    return report


def _hierarchy_certificate(
    content: str,
    parents: Sequence[tuple[str, int]],
    dependencies: dict[str, list[list[str | int]]],
    child_edges: Sequence[dict[str, object]],
) -> str:
    payload = json.dumps(
        {
            "edge_certificate": make_edge_certificate(content, parents, dependencies),
            "child_edges": list(child_edges),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def compact_hierarchy(
    fabric: "MemoryFabric",
    episode_id: str,
    agent_id: str,
    *,
    leaf_size: int = 8,
    tenant_id: str = DEFAULT_TENANT,
) -> HierarchicalCompactionReport:
    """Build deterministic leaf summaries and a certified history root.

    Root lineage includes both leaf summaries and original versions. This
    deliberately gives corrections a short invalidation path while preserving
    independently usable sibling leaves.
    """
    from .navigation import _visible

    if not agent_id or not tenant_id:
        raise CompactionRefused("compaction requires agent and tenant identities")
    if isinstance(leaf_size, bool) or not isinstance(leaf_size, int) or leaf_size < 2:
        raise ValueError("leaf_size must be an integer of at least 2")
    with fabric._transaction():
        eligible = set(_visible(fabric, agent_id, tenant_id)) - fabric.state.erased
        usable = [
            memory
            for memory in session_memories(fabric, episode_id)
            if memory.tenant_id == tenant_id
            and visible_to(memory, agent_id, fabric.state)
            and memory.id in eligible
        ]
    usable.sort(key=lambda memory: (memory.created_at, memory.id, memory.version))
    if len(usable) <= leaf_size:
        raise CompactionRefused(
            f"hierarchical compaction requires more than {leaf_size} active source memories"
        )
    groups = [usable[start:start + leaf_size] for start in range(0, len(usable), leaf_size)]
    label = session_label(fabric, episode_id)
    leaf_plans: list[tuple[list["Memory"], str, dict[str, list[list[str | int]]], str]] = []
    for index, group in enumerate(groups):
        text = f"Session summary ({label} leaf {index + 1}): " + extractive(
            group, find_conflicts(group)
        )
        try:
            dependencies = reconstruct_dependency_map(text, group)
        except DependencyMapRefused as exc:
            raise CompactionRefused(f"leaf summary dependency map failed: {exc}") from exc
        parent_versions = [(memory.id, memory.version) for memory in group]
        certificate = make_edge_certificate(text, parent_versions, dependencies)
        leaf_plans.append((group, text, dependencies, certificate))

    root_disputes = find_conflicts(usable)
    root_text = f"Session summary ({label}): " + extractive(usable, root_disputes)
    try:
        root_dependencies = reconstruct_dependency_map(root_text, usable)
    except DependencyMapRefused as exc:
        raise CompactionRefused(f"root summary dependency map failed: {exc}") from exc

    narrowest = min((memory.scope for memory in usable), key=lambda scope: scope.rank)
    leaf_ids: list[str] = []
    leaf_edges: list[dict[str, object]] = []
    certificates: dict[str, str] = {}
    with fabric._transaction():
        eligible = set(_visible(fabric, agent_id, tenant_id)) - fabric.state.erased
        for memory in usable:
            current = fabric.state.memories.get(memory.id)
            if (memory.id not in eligible or current is None
                    or current.version != memory.version
                    or current.lifecycle_state not in EXPOSABLE_STATES):
                raise CompactionRefused(
                    "hierarchy sources changed during summarization; retry with current evidence"
                )
        for index, (group, text, dependencies, certificate) in enumerate(leaf_plans):
            leaf_scope = min((memory.scope for memory in group), key=lambda scope: scope.rank)
            summary_id = fabric.derive(
                agent_id,
                text,
                parents=[memory.id for memory in group],
                method=ProvenanceMethod.CONSOLIDATED,
                context={
                    "kind": "derived_claim",
                    "summary_hierarchy": episode_id,
                    "hierarchy_node": "leaf",
                    "hierarchy_index": index,
                    "summary_dependencies": dependencies,
                    "summary_edge_certificate": certificate,
                },
                scope=leaf_scope,
            )
            if fabric.state.memories[summary_id].lifecycle_state not in EXPOSABLE_STATES:
                raise CompactionRefused("a hierarchy leaf did not pass the ingest screen")
            leaf_ids.append(summary_id)
            certificates[summary_id] = certificate
            leaf_edges.append({
                "summary_id": summary_id,
                "summary_version": fabric.state.memories[summary_id].version,
                "source_versions": [[memory.id, memory.version] for memory in group],
                "certificate": certificate,
            })

        direct_parents = leaf_ids + [memory.id for memory in usable]
        direct_parent_versions = [
            (summary_id, fabric.state.memories[summary_id].version) for summary_id in leaf_ids
        ] + [(memory.id, memory.version) for memory in usable]
        root_certificate = _hierarchy_certificate(
            root_text, direct_parent_versions, root_dependencies, leaf_edges
        )
        root_id = fabric.derive(
            agent_id,
            root_text,
            parents=direct_parents,
            method=ProvenanceMethod.CONSOLIDATED,
            context={
                "kind": "derived_claim",
                "compaction_of": episode_id,
                "summary_hierarchy": episode_id,
                "hierarchy_node": "root",
                "hierarchy_leaf_ids": leaf_ids,
                "summary_source_versions": [
                    [memory.id, memory.version] for memory in usable
                ],
                "summary_dependencies": root_dependencies,
                "summary_edge_certificates": leaf_edges,
                "summary_hierarchy_certificate": root_certificate,
                "summary_edge_certificate": None,
            },
            scope=narrowest,
        )
        if fabric.state.memories[root_id].lifecycle_state not in EXPOSABLE_STATES:
            raise CompactionRefused("the hierarchy root did not pass the ingest screen")
    certificates[root_id] = root_certificate
    return HierarchicalCompactionReport(
        episode_id=episode_id,
        root_summary_id=root_id,
        leaf_summary_ids=leaf_ids,
        leaf_source_groups=[[memory.id for memory in group] for group in groups],
        certificates=certificates,
    )


def verify_hierarchical_summary(
    fabric: "MemoryFabric", root_summary_id: str
) -> dict[str, object]:
    """Verify the root/leaf certificates and exact active source partition."""
    root = fabric.state.memories[root_summary_id]
    context = root.context or {}
    if (root.lifecycle_state not in EXPOSABLE_STATES
            or context.get("hierarchy_node") != "root"):
        raise CompactionRefused("hierarchy root is not an active certified root")
    child_edges = context.get("summary_edge_certificates")
    source_refs = context.get("summary_source_versions")
    if not isinstance(child_edges, list) or len(child_edges) < 2 or not isinstance(source_refs, list):
        raise CompactionRefused("hierarchy root has no complete child certificate list")
    flattened: list[tuple[str, int]] = []
    expected_children: set[tuple[str, int]] = set()
    for edge in child_edges:
        if not isinstance(edge, dict):
            raise CompactionRefused("malformed hierarchy child certificate")
        child_id = str(edge.get("summary_id"))
        child = fabric.state.memories.get(child_id)
        if (child is None or child.lifecycle_state not in EXPOSABLE_STATES
                or child.version != int(edge.get("summary_version", -1))):
            raise CompactionRefused("a hierarchy leaf is stale or unavailable")
        if (child.context or {}).get("summary_hierarchy") != context.get("summary_hierarchy"):
            raise CompactionRefused("hierarchy leaf belongs to another root")
        child_sources = edge.get("source_versions")
        if not isinstance(child_sources, list):
            raise CompactionRefused("hierarchy leaf certificate has no source versions")
        refs = [(str(pair[0]), int(pair[1])) for pair in child_sources]
        if set(child.provenance.parents) != set(refs):
            raise CompactionRefused("hierarchy leaf parents differ from its certificate")
        source_memories = []
        for memory_id, version in refs:
            source = fabric.state.memories.get(memory_id)
            if (source is None or source.version != version
                    or source.lifecycle_state not in EXPOSABLE_STATES):
                raise CompactionRefused("a hierarchy source version is no longer active")
            source_memories.append(source)
        verify_stored_dependency_map(child, source_memories)
        child_certificate = make_edge_certificate(
            child.content, refs, (child.context or {}).get("summary_dependencies", {})
        )
        if (child_certificate != edge.get("certificate")
                or child_certificate != (child.context or {}).get("summary_edge_certificate")):
            raise CompactionRefused("hierarchy leaf edge certificate digest mismatch")
        flattened.extend(refs)
        expected_children.add((child_id, child.version))

    normalized_source_refs = [(str(pair[0]), int(pair[1])) for pair in source_refs]
    if flattened != normalized_source_refs or len(flattened) != len(set(flattened)):
        raise CompactionRefused("hierarchy leaves do not partition the certified source versions")
    expected_parents = expected_children | set(normalized_source_refs)
    if set(root.provenance.parents) != expected_parents:
        raise CompactionRefused("root provenance differs from its explicit edge certificate")
    root_sources = [fabric.state.memories[mid] for mid, _ in normalized_source_refs]
    verify_stored_dependency_map(root, root_sources)
    root_parent_versions = list(root.provenance.parents)
    root_certificate = _hierarchy_certificate(
        root.content,
        root_parent_versions,
        context.get("summary_dependencies", {}),
        child_edges,
    )
    if root_certificate != context.get("summary_hierarchy_certificate"):
        raise CompactionRefused("hierarchy root certificate digest mismatch")
    return {
        "root_summary_id": root.id,
        "leaf_summary_ids": sorted(expected_children),
        "source_versions": normalized_source_refs,
        "certificate": root_certificate,
    }


def stale_summaries(fabric: "MemoryFabric") -> list[tuple[str, str]]:
    """Compaction summaries withdrawn or contested because an input changed: (summary, episode)."""
    out = []
    for memory in fabric.state.memories.values():
        episode = (memory.context or {}).get("compaction_of")
        if episode and memory.lifecycle_state not in EXPOSABLE_STATES:
            newer = [m for m in fabric.state.memories.values()
                     if (m.context or {}).get("compaction_of") == episode
                     and m.lifecycle_state in EXPOSABLE_STATES]
            if not newer:
                out.append((memory.id, str(episode)))
    return out


def recompact(fabric: "MemoryFabric", agent_id: str) -> list[CompactionReport]:
    """Write a fresh summary for every episode whose summary lost an input.

    A correction to one input contests the whole summary, which is right: it
    states a value that is no longer believed. But it also hides every other
    fact the summary held, and the C1 pilot measured that cost. Re-compacting
    from the inputs still usable restores them; the old summary stays
    contested, in the log, for audit. The background manager runs it.
    """
    reports = []
    for _, episode in stale_summaries(fabric):
        try:
            reports.append(compact_session(fabric, episode, agent_id=agent_id))
        except CompactionRefused:
            continue
    return reports


def summary_for(fabric: "MemoryFabric", episode_id: str) -> "Memory | None":
    """The session's current, usable summary: what a handoff to a later session reads first."""
    found = [m for m in fabric.state.memories.values()
             if (m.context or {}).get("compaction_of") == episode_id
             and m.lifecycle_state in EXPOSABLE_STATES]
    return max(found, key=lambda m: m.created_at) if found else None


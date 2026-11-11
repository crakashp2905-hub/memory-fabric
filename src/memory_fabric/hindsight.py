"""Hindsight: a withdrawal changes what the store believes about the rest of a source (T2).

The temporal-reasoning review (2026-10-18) separated two claims. This is the
backward one. When a memory is withdrawn as **false**, the store has learned
something about its author, not only about that memory. Retraction acts on
the memory, and its derived conclusions, and stops there. The author's
*other* memories, which nothing has yet contradicted, stay exactly as
trusted as before.

A source caught by the prompt-injection screen counts as discredited too:
an author who injects is hostile, whatever their other notes look like.

`suspects` re-reads them in hindsight. Every active memory whose original
author (`conflicts.author`, so imports resolve to the writer) has had a
memory withdrawn on a falsity basis is suspect. A caller can then:

- **flag** them (`annotate`), so an agent sees that the source has been wrong
  before;
- **withhold** them (`withhold`) until someone reviews them.

**The cost, stated:** an honest author who made one honest mistake becomes a
suspect too, and so does every valid note they wrote. T2 measures that cost
with a control family, an honest technician with one withdrawn mistake, so
it is weighed rather than assumed away.
"""

from __future__ import annotations

__stability__ = "beta"

from typing import TYPE_CHECKING, Iterable, Sequence

from .conflicts import author
from .events import EventType
from .model import LifecycleState

if TYPE_CHECKING:  # pragma: no cover
    from .fabric import MemoryFabric
    from .model import Memory

FALSITY = ("contradicted", "detected as false", "wrong", "poison", "prompt injection")
HOSTILE = ("prompt injection", "hostile")
"""Signals no honest author produces. A contradicted withdrawal can be an honest mistake."""
INGESTED_FROM = "ingested_from"
"""Context key naming where an agent got the content it stored (a URL, a
document id, a tool). When present, a memory withdrawn as hostile or false
discredits *that origin*, not the agent that stored it: an honest agent that
saved a poisoned page has not become hostile. Found by O1, where discrediting
the storing agent withheld 65 true notes by six honest agents
(research/results/o1-live-poisonworld.md)."""


def source_ref(memory: "Memory") -> str:
    """The source a withdrawal of this memory reflects on.

    `ingested:<origin>` when the writer declared where the content came from,
    otherwise the author (`conflicts.author`), which is the pre-O1 behaviour.
    """
    origin = memory.context.get(INGESTED_FROM)
    if isinstance(origin, str) and origin.strip():
        return f"ingested:{origin.strip()}"
    return author(memory)


def discredited(memory: "Memory", bad: "set[str] | frozenset[str]") -> bool:
    """Whether a memory falls under a discredited source: its declared origin,
    or its author (an explicit notice about the author still applies)."""
    return author(memory) in bad or source_ref(memory) in bad


SUSPECT = "[SOURCE WAS WRONG BEFORE: another note by this author was withdrawn as false]"


def discredited_authors(fabric: "MemoryFabric", signals: Sequence[str] = FALSITY,
                        federated: bool = True) -> set[str]:
    """Authors with a memory withdrawn on one of these grounds.

    `signals=HOSTILE` discredits only sources caught doing something no honest
    author does (T2's dev pilot: discrediting on any falsity withheld every
    valid note by an honest technician who made one mistake).
    """
    out: set[str] = set()
    # A hostile finding recorded here, or a peer's authenticated notice about
    # one of its sources (`SourceNotice`): the signal that never left the
    # origin store before (T2).
    for event in fabric.log.read_types([EventType.SOURCE_DISCREDITED]):
        payload = event.payload
        from_peer = payload.get("origin_store_id") != fabric.store_id
        if from_peer and not federated:
            continue
        if payload.get("authorised") and any(word in str(payload.get("signal", ""))
                                             for word in ("hostile",)):
            if any(s in ("prompt injection", "hostile") for s in signals):
                out.add(str(payload["author_ref"]))
    for event in fabric.log.read_types([EventType.LIFECYCLE_CHANGED]):
        payload = event.payload
        if payload.get("to") not in (LifecycleState.QUARANTINED.value,
                                      LifecycleState.DEPRECATED.value):
            continue
        # Both fields: a recipient records the basis as `retracted_at_origin`
        # and the origin's basis in the reason, so reading the basis alone
        # missed every cross-store withdrawal (found on T2's dev world).
        said = f"{payload.get('basis') or ''} {payload.get('reason') or ''}".lower()
        if not any(word in said for word in signals):
            continue
        memory = fabric.state.memories.get(payload.get("memory_id", ""))
        if memory is not None:
            out.add(source_ref(memory))
    return out


def suspects(fabric: "MemoryFabric", memories: Iterable["Memory"] | None = None,
             signals: Sequence[str] = FALSITY, federated: bool = True) -> set[str]:
    """Ids of active memories whose author has been discredited."""
    bad = discredited_authors(fabric, signals, federated)
    pool = fabric.state.memories.values() if memories is None else memories
    return {m.id for m in pool
            if m.lifecycle_state is LifecycleState.ACTIVE and discredited(m, bad)}


def annotate(fabric: "MemoryFabric", memories: Sequence["Memory"]) -> list[str]:
    flagged = suspects(fabric, memories)
    return [f"{SUSPECT} {m.content}" if m.id in flagged else m.content for m in memories]


def withhold(fabric: "MemoryFabric", memories: Sequence["Memory"],
             signals: Sequence[str] = FALSITY, federated: bool = True) -> list[str]:
    flagged = suspects(fabric, memories, signals, federated)
    return [m.content for m in memories if m.id not in flagged]

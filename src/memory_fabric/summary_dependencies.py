"""Fact-level provenance checks for generated session summaries."""

from __future__ import annotations

__stability__ = "experimental"

import json
import re
from collections import defaultdict
from typing import TYPE_CHECKING, Sequence

from .conflicts import claim
from .model import LifecycleState

if TYPE_CHECKING:
    from .model import Memory


class DependencyMapRefused(ValueError):
    """A summary contains an unsupported fact or loses a source fact."""


def _signature(text: str) -> str | None:
    identifiers, words, values = claim(text)
    if not identifiers and not values:
        return None
    return json.dumps(
        [sorted(identifiers), sorted(words), sorted(values)],
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+|;\s*", text) if part.strip()]


def _summary_fact_texts(text: str, sources: Sequence["Memory"]) -> list[str]:
    """Read fact-bearing clauses, decoding the supported lossless envelope exactly."""
    body = re.sub(r"^Session summary \([^)]*\):\s*", "", text)
    try:
        envelope = json.loads(body)
    except (TypeError, ValueError):
        envelope = None
    if isinstance(envelope, dict) and set(envelope) == {"dictionary", "records"}:
        from .lossless_compaction import decode_records

        try:
            decoded = decode_records(body)
        except (TypeError, ValueError) as exc:
            raise DependencyMapRefused("lossless summary could not be decoded exactly") from exc
        if decoded != [memory.content for memory in sources]:
            raise DependencyMapRefused("lossless summary records do not match source versions")
        return [sentence for record in decoded for sentence in _sentences(record)]

    body = re.sub(r"Disputed, unresolved:\s*", "", body)
    body = re.sub(r"\s*\(from [^)]*\)", "", body)
    return _sentences(body)


def reconstruct_dependency_map(
    summary_content: str, sources: Sequence["Memory"]
) -> dict[str, list[list[str | int]]]:
    """Map every consequential summary fact to exact, active source versions.

    Fact identity is the conflict detector's normalized identifiers, content
    words, and numeric values. The mapping is deliberately conservative: a
    paraphrase that cannot be tied to an exact source signature is refused.
    """
    by_fact: dict[str, set[tuple[str, int]]] = defaultdict(set)
    source_facts: set[str] = set()
    for memory in sources:
        if memory.lifecycle_state is not LifecycleState.ACTIVE:
            raise DependencyMapRefused(
                f"source {memory.id!r} version {memory.version} is not active"
            )
        for sentence in _sentences(memory.content):
            fact = _signature(sentence)
            if fact is not None:
                source_facts.add(fact)
                by_fact[fact].add((memory.id, memory.version))

    summary_facts: set[str] = set()
    for sentence in _summary_fact_texts(summary_content, sources):
        fact = _signature(sentence)
        if fact is not None:
            summary_facts.add(fact)

    missing = source_facts - summary_facts
    unsupported = summary_facts - source_facts
    if missing:
        raise DependencyMapRefused(f"summary omitted source facts: {sorted(missing)}")
    if unsupported:
        raise DependencyMapRefused(f"summary contains unsupported facts: {sorted(unsupported)}")
    return {
        fact: [[memory_id, version] for memory_id, version in sorted(by_fact[fact])]
        for fact in sorted(summary_facts)
    }


def verify_stored_dependency_map(
    summary: "Memory", sources: Sequence["Memory"]
) -> dict[str, list[list[str | int]]]:
    """Reconstruct and compare a persisted summary's fact-to-version map."""
    reconstructed = reconstruct_dependency_map(summary.content, sources)
    stored = (summary.context or {}).get("summary_dependencies")
    if stored != reconstructed:
        raise DependencyMapRefused("stored dependency map differs from reconstructed oracle map")
    parents = set(summary.provenance.parents)
    mapped = {
        (str(memory_id), int(version))
        for refs in reconstructed.values()
        for memory_id, version in refs
    }
    if not mapped <= parents:
        raise DependencyMapRefused("a fact dependency is not bound by summary parent versions")
    return reconstructed

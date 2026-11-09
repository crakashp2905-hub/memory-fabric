"""Deterministic query routing between measured retrieval arms.

Routing is deliberately conservative.  The dependency-free hashing embedder
lost to lexical retrieval on both SciFact and full-history LongMemEval, so an
``auto`` request never gives it a fusion vote.  With a trained embedder,
identifier and temporal lookups remain lexical while semantic and multi-hop
questions use hybrid retrieval.
"""

from __future__ import annotations

__stability__ = "beta"

import re
from dataclasses import dataclass

_IDENTIFIER = re.compile(
    r"(?:\b[A-Z]{1,8}[-_][A-Z0-9][A-Z0-9_-]*\b|\b[a-z]+-\d+\b|\b\d+(?:\.\d+)?\s*(?:bar|psi|mm|cm|m|kg|ms|s)\b)",
    re.IGNORECASE,
)
_TEMPORAL = re.compile(
    r"\b(?:when|before|after|first|last|latest|current|currently|previous|"
    r"yesterday|today|tomorrow|year|month|week|date|time)\b",
    re.IGNORECASE,
)
_MULTI_HOP = re.compile(
    r"\b(?:because|therefore|depends on|based on|relationship|connect|compare|"
    r"difference between|how does|why does|what caused)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Route:
    query_type: str
    method: str
    reason: str


def route(query: str, *, trained_embedder: bool) -> Route:
    """Choose a retrieval arm without a learned or tuned threshold."""
    if _IDENTIFIER.search(query):
        return Route("identifier", "lexical", "exact identifiers favour lexical retrieval")
    if _TEMPORAL.search(query):
        return Route("temporal", "lexical", "time filtering and exact events favour lexical retrieval")
    if _MULTI_HOP.search(query):
        if trained_embedder:
            return Route("multi_hop", "hybrid", "trained semantic recall can nominate connectors")
        return Route("multi_hop", "lexical", "hashing vectors are not admitted to fusion")
    if trained_embedder:
        return Route("semantic", "hybrid", "trained semantic and lexical arms are both qualified")
    return Route("semantic", "lexical", "hashing vectors are not admitted to fusion")

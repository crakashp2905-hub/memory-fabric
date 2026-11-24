"""Semantic advisory for counterfactual decision memory (VEGA-CDM).

Everything in this package produces *proposals*: relevance and support labels,
candidate causal edges, intervention priorities and recovery suggestions. None
of it reads the event log directly, writes to the store, grants a tool, or
labels a hypothesis as a verified effect. Evidence enters only as
:class:`packets.SemanticEvidencePacket` built from an authorized retrieval, and
a proposal becomes a validated effect only through the existing deterministic
replay and independent verifier (``causal_replay.replay`` / ``verifier``).

The epistemic tiers are fixed in :mod:`.taxonomy`; a model score can reach at
most ``TEXTUAL_RELEVANCE`` or ``HYPOTHESIS``.
"""

from __future__ import annotations

__stability__ = "experimental"

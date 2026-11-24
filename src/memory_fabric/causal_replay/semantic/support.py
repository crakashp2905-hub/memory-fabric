"""Semantic relevance and claim support over an authorized packet bundle (VEGA S03).

The advisor proposes a label per (evidence version, claim) pair. Deterministic
code keeps the last word:

* **Exact guards** (:func:`exact_guard`): an identifier or a quantity in the
  claim that the evidence does not carry, or carries differently, caps the
  label. A paraphrase may be SUPPORTED; ``unit-7`` is never ``unit-17`` and
  ``61 C`` is never ``16 C`` (VEGA-CDM-033).
* **Independence** is counted from packet source roots, never from the model,
  so paraphrased copies of one origin stay one source (036).
* **Ambiguity is kept**: an abstention, a conformal set with more than one
  option, an unbound answer or an unavailable advisor yields ``UNKNOWN`` with
  route ``retrieve_more`` instead of a forced winner (039).
* **Multi-label hypotheses** are asked one at a time, so sensor bias and real
  overheating can both be supported by the same evidence (038).

A cheap lexical prefilter (:func:`lexical_score`) decides which pairs are
clear enough to skip the advisor; only the ambiguous band is sent (037).
"""

from __future__ import annotations

__stability__ = "experimental"

import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from .advice import Advisor, Answer, Question
from .packets import PacketBundle, SemanticEvidencePacket

SUPPORT_LABELS = ("supported", "contradicted", "unknown", "incomparable")
RELEVANCE_LABELS = ("relevant", "partial", "irrelevant")
_IDENT = re.compile(r"\b(?=[A-Za-z0-9-]*\d)(?=[A-Za-z0-9-]*[A-Za-z])[A-Za-z0-9]+(?:-[A-Za-z0-9]+)+\b"
                    r"|\b[A-Z]{1,4}-?\d+[A-Za-z]?\b")
_QTY = re.compile(r"(?<![\w.])(-?\d+(?:\.\d+)?)\s*(%|[A-Za-z]{1,4}\b)?")
_NEGATION = re.compile(r"\b(not|no|never|without|isn't|wasn't|doesn't|didn't|cannot|can't)\b", re.I)
_WORD = re.compile(r"[a-z0-9]+")
_STOP = frozenset("the a an of to is are was were in on at for and or by with from this that it as be".split())


def support_question(claim: str) -> Question:
    return Question("claim_support", "choice",
                    f"How does this CURRENT authorized evidence relate to the claim: {claim}",
                    {"supported": "This evidence directly supports the claim at its scoped time.",
                     "contradicted": "This evidence directly conflicts with the claim.",
                     "unknown": "The link cannot be determined from this evidence.",
                     "incomparable": "The evidence is about a different entity, time or quantity."})


def relevance_question(query: str) -> Question:
    return Question("relevance", "choice", f"Is this evidence relevant to: {query}",
                    {"relevant": "directly about the question", "partial": "related but incomplete",
                     "irrelevant": "not about the question"})


def identifiers(text: str) -> set[str]:
    return {m.group(0).lower() for m in _IDENT.finditer(text)}


def quantities(text: str) -> set[tuple[float, str]]:
    out = set()
    for m in _QTY.finditer(text):
        unit = (m.group(2) or "").lower()
        out.add((float(m.group(1)), unit))
    return out


def exact_guard(claim: str, evidence: str) -> str | None:
    """The cap the exact guards put on a support label, or None if they allow anything.

    ``incomparable``: the claim names an identifier the evidence does not.
    ``not_supported``: the claim states a quantity the evidence gives differently.
    """
    claim_ids, ev_ids = identifiers(claim), identifiers(evidence)
    if claim_ids and not claim_ids <= ev_ids:
        return "incomparable"
    claim_q = {q for q in quantities(claim) if q[1]}
    ev_q = {q for q in quantities(evidence) if q[1]}
    units = {u for _, u in claim_q}
    if claim_q and any(u in {eu for _, eu in ev_q} for u in units) and not claim_q <= ev_q:
        return "not_supported"
    if bool(_NEGATION.search(claim)) != bool(_NEGATION.search(evidence)) and claim_q and claim_q <= ev_q:
        return "not_supported"
    return None


def lexical_score(claim: str, evidence: str) -> float:
    a = {w for w in _WORD.findall(claim.lower()) if w not in _STOP}
    b = {w for w in _WORD.findall(evidence.lower()) if w not in _STOP}
    return len(a & b) / len(a) if a else 0.0


@dataclass(frozen=True)
class SupportProposal:
    evidence_ref: str
    origin_root: str
    claim: str
    label: str
    route: str  # accept | retrieve_more | none
    tier: str
    answer_status: str
    probs: Mapping[str, float]
    prediction_set: tuple[str, ...]
    guard: str | None
    receipt_digest: str | None
    source: str  # advisor | lexical_prefilter | guard


def _from_answer(packet: SemanticEvidencePacket, claim: str, answer: Answer, guard: str | None,
                 receipt: Mapping[str, Any]) -> SupportProposal:
    label, route = "unknown", "retrieve_more"
    if answer.decisive and answer.value in SUPPORT_LABELS:
        label, route = str(answer.value), "accept"
    if guard == "incomparable":
        label, route = "incomparable", "none"
    elif guard == "not_supported" and label == "supported":
        label, route = "unknown", "retrieve_more"
    return SupportProposal(packet.ref, packet.origin_root, claim, label, route,
                           "TEXTUAL_RELEVANCE", answer.status, dict(answer.probs),
                           answer.prediction_set, guard, receipt.get("receipt_digest"), "advisor")


def assess(bundle: PacketBundle, claim: str, advisor: Advisor, *,
           clear_low: float = 0.0, ask_band: tuple[float, float] = (0.0, 1.01)
           ) -> list[SupportProposal]:
    """One support proposal per packet. Pairs outside ``ask_band`` skip the advisor.

    A pair with lexical overlap at or below ``clear_low`` is labelled
    ``unknown``/``none`` without a model call.
    """
    out: list[SupportProposal] = []
    question = {"claim_support": support_question(claim)}
    for packet in bundle.packets:
        guard = exact_guard(claim, packet.visible_text)
        score = lexical_score(claim, packet.visible_text)
        if guard == "incomparable":
            out.append(SupportProposal(packet.ref, packet.origin_root, claim, "incomparable", "none",
                                       "TEXTUAL_RELEVANCE", "NOT_ASKED", {}, (), guard, None, "guard"))
            continue
        if score <= clear_low or not ask_band[0] <= score < ask_band[1]:
            out.append(SupportProposal(packet.ref, packet.origin_root, claim, "unknown", "none",
                                       "TEXTUAL_RELEVANCE", "NOT_ASKED", {}, (), guard, None,
                                       "lexical_prefilter"))
            continue
        advice = advisor.decide(f"Claim: {claim}\nEvidence: {packet.ref}: {packet.visible_text}",
                                question)
        out.append(_from_answer(packet, claim, advice.answers["claim_support"], guard,
                                advice.receipt))
    return out


def assess_hypotheses(bundle: PacketBundle, hypotheses: Sequence[str], advisor: Advisor
                      ) -> dict[str, list[SupportProposal]]:
    """Each hypothesis assessed on its own: no forced exclusivity between them (VEGA-CDM-038)."""
    return {h: assess(bundle, h, advisor) for h in hypotheses}


def corroboration(proposals: Iterable[SupportProposal]) -> dict[str, int]:
    """Independent roots per label. Copies of one origin count once, whatever the model said."""
    roots: dict[str, set[str]] = {}
    for p in proposals:
        if p.route == "accept":
            roots.setdefault(p.label, set()).add(p.origin_root)
    return {label: len(r) for label, r in roots.items()}


def backstop(proposals: Sequence[SupportProposal], readable_refs: set[str]) -> list[SupportProposal]:
    """Structural answerability wins: a proposal on evidence no longer readable is dropped (035)."""
    return [p for p in proposals if p.evidence_ref in readable_refs]

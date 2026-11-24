"""The epistemic taxonomy every semantic artifact is tagged with (VEGA-CDM-002, 010).

Ordered from weakest to strongest. A tag says what kind of evidence stands behind
a statement, not how confident anyone is in it:

``TEXTUAL_RELEVANCE``
    a model or a lexical score says the text is about the claim.
``OBSERVED_DEPENDENCE``
    the provenance log shows the decision was exposed to, or relied on, the evidence.
``HYPOTHETICAL_EFFECT``
    a proposal that changing the evidence would change the decision; nothing ran.
``VALIDATED_COUNTERFACTUAL``
    a deterministic replay under registered assumptions, checked by the independent
    verifier, changed the decision. Simulator-conditional, never physical.
``REAL_WORLD_CAUSAL``
    an independently graded terminal outcome in a registered real study. Nothing in
    this repository has produced one; :func:`require_at_most` refuses it by default.

Evidence levels for results (scripted vs model vs replicated vs deployed) are a
separate axis, :data:`EVIDENCE_LEVELS`.
"""

from __future__ import annotations

__stability__ = "experimental"

from typing import Mapping

TIERS = ("TEXTUAL_RELEVANCE", "OBSERVED_DEPENDENCE", "HYPOTHETICAL_EFFECT",
         "VALIDATED_COUNTERFACTUAL", "REAL_WORLD_CAUSAL")
MODEL_CEILING = "HYPOTHETICAL_EFFECT"
"""The strongest tier a model output alone may carry."""

EVIDENCE_LEVELS = ("CONTRACT", "SCRIPTED", "FAKE_BACKEND_NOT_EVIDENCE", "VEGA_MODEL_SMOKE",
                   "LOCAL_MODEL_STUDY", "CONFIRMATORY", "INDEPENDENTLY_REPLICATED", "DEPLOYED")
EFFICACY_LEVELS = frozenset({"LOCAL_MODEL_STUDY", "CONFIRMATORY", "INDEPENDENTLY_REPLICATED",
                             "DEPLOYED"})


class TaxonomyError(ValueError):
    """A statement claims a stronger tier than its evidence carries."""


def rank(tier: str) -> int:
    if tier not in TIERS:
        raise TaxonomyError(f"unknown epistemic tier {tier!r}")
    return TIERS.index(tier)


def require_at_most(tier: str, ceiling: str) -> str:
    if rank(tier) > rank(ceiling):
        raise TaxonomyError(f"{tier} exceeds the permitted ceiling {ceiling}")
    return tier


def model_tier(tier: str) -> str:
    """Validate a tier attached to a model output: never above a hypothesis."""
    return require_at_most(tier, MODEL_CEILING)


def check_report_level(report: Mapping[str, object]) -> list[str]:
    """Problems with a result report's claimed evidence level (VEGA-CDM-010).

    A report claiming an efficacy level must carry a model digest, real inference
    and a registration digest; a scripted or fake-backend report must not use
    efficacy words in its verdict.
    """
    level = report.get("evidence_level")
    problems: list[str] = []
    if level not in EVIDENCE_LEVELS:
        return [f"unknown evidence level {level!r}"]
    if level in EFFICACY_LEVELS or level == "VEGA_MODEL_SMOKE":
        if not report.get("model_digest"):
            problems.append(f"{level} needs a model digest")
        if report.get("real_inference") is not True:
            problems.append(f"{level} needs real_inference: true")
    if level in EFFICACY_LEVELS and not report.get("registration_digest"):
        problems.append(f"{level} needs a frozen registration digest")
    verdict = str(report.get("verdict", "")).upper()
    if level not in EFFICACY_LEVELS and any(word in verdict for word in
                                            ("EFFECT_SUPPORTED", "SUPERIOR", "QUALIFIED", "IMPROVES")):
        problems.append(f"a {level} report cannot claim {verdict}")
    return problems

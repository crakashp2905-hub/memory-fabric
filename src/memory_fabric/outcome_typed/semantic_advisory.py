"""Optional semantic recovery advice inside the canonical outcome runtime (VEGA S09).

Not a fourth outcome stack: this module only annotates what
:class:`~.api.OutcomeAPI` already decided. Modes (VEGA-CDM-008):

``OFF`` (default)
    no advisor call; every response is byte-identical to a runtime without it (091).
``SHADOW``
    the advisor is called and its suggestion is logged on the API object, never returned.
``ADVISORY``
    the suggestion is returned beside the authoritative diagnosis, labelled a proposal.
``QUALIFIED``
    refused here. It would need a registered efficacy result, and the development
    run with the 0.8B reader increased unsafe actions (``research/results/vega-cdm``).

The authoritative failure cause (:data:`FAILURE_CAUSES`) is mapped from the
runtime's own diagnosis codes; the advisor can add a ranked proposal but cannot
rewrite it (092). Suggestions come only from :data:`RECOVERY_CATALOG`, a
read-only host list; anything else is discarded (093, 097). No suggestion
carries a permission, an evidence write or a tool call.
"""

from __future__ import annotations

__stability__ = "experimental"

from typing import Any, Mapping

from ..causal_replay.semantic.advice import Advisor, Question

MODES = ("OFF", "SHADOW", "ADVISORY", "QUALIFIED")
RECOVERY_CATALOG = ("REFRESH", "RE_RETRIEVE", "INSPECT_PROVENANCE", "ASK", "REPLAN", "ABSTAIN")
FAILURE_CAUSES = ("MISSING", "STALE", "WITHHELD", "CONTESTED", "IRRELEVANT", "NON_REPLAYABLE")
CAUSE_OF = {
    "withdrawn": "STALE", "superseded": "STALE", "stale_lease": "STALE",
    "contested": "CONTESTED", "contradictory_observations": "CONTESTED",
    "not_available": "WITHHELD", "no_permission": "WITHHELD", "untrusted": "WITHHELD",
    "no_evidence": "MISSING", "retrieval_miss": "MISSING",
    "malformed_assertion": "IRRELEVANT", "tool": "IRRELEVANT",
    "budget": "NON_REPLAYABLE", "effect_unknown": "NON_REPLAYABLE",
}


class AdvisoryConfigError(ValueError):
    pass


def check_mode(mode: str) -> str:
    if mode not in MODES:
        raise AdvisoryConfigError(f"unknown semantic advisory mode {mode!r}")
    if mode == "QUALIFIED":
        raise AdvisoryConfigError("QUALIFIED needs a registered efficacy result; none exists")
    return mode


def failure_cause(diagnosis: str | None) -> str | None:
    """The authoritative cause, from the runtime's diagnosis code only."""
    if diagnosis is None:
        return None
    return CAUSE_OF.get(diagnosis, "NON_REPLAYABLE")


def question() -> Question:
    return Question("next_step", "choice", "Which ALLOWED recovery step should be considered next?",
                    {"refresh": "re-check the current version of the evidence used",
                     "re_retrieve": "retrieve current authorized evidence again",
                     "inspect_provenance": "check where the evidence came from and whether copies agree",
                     "ask": "ask the host or an operator for a missing fact or access",
                     "replan": "plan again on what is current",
                     "abstain": "stop: the evidence is not sufficient"})


def suggest(advisor: Advisor, diagnosis: str, status: str) -> dict[str, Any]:
    """One ranked proposal from the catalog, or ``UNAVAILABLE``; never a permission."""
    q = {"next_step": question()}
    advice = advisor.decide(f"Task status: {status}. Runtime diagnosis: {diagnosis}.", q)
    answer = advice.answers["next_step"]
    choice = str(answer.value).upper() if answer.value is not None else None
    ranked = sorted(answer.probs, key=lambda k: -answer.probs[k]) if answer.probs else []
    if answer.status not in ("OK", "ABSTAIN") or choice not in RECOVERY_CATALOG:
        return {"status": "UNAVAILABLE", "reason": answer.reason or "no catalog step",
                "kind": "MODEL_PROPOSAL", "receipt_digest": advice.receipt.get("receipt_digest")}
    return {"status": "ABSTAINED" if answer.status == "ABSTAIN" else "PROPOSED",
            "kind": "MODEL_PROPOSAL", "step": choice,
            "ranked": [r.upper() for r in ranked if r.upper() in RECOVERY_CATALOG],
            "evidence_level": advice.receipt.get("evidence_level"),
            "receipt_digest": advice.receipt.get("receipt_digest"),
            "grants": None}


def annotate(result: Mapping[str, Any], *, advisor: Advisor | None, mode: str,
             shadow_log: list[dict[str, Any]]) -> dict[str, Any]:
    """Add advice to an ``inspect_failure`` result according to ``mode``; OFF returns it untouched."""
    out = dict(result)
    if mode == "OFF" or advisor is None or result.get("failure") is None:
        return out
    out_cause = failure_cause(str(result["failure"]))
    proposal = suggest(advisor, str(result["failure"]), str(result.get("status")))
    if mode == "SHADOW":
        shadow_log.append({"task_id": result.get("task_id"), "cause": out_cause, **proposal})
        return out
    out["semantic_advisory"] = {"cause": out_cause, **proposal}
    return out

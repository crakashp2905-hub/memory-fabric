"""Evidence diagnosis before refusal (W06-01, W06-02, W06-03, W06-07, W06-09).

Why could the agent not act? Nine typed answers, on three axes that are never
conflated:

* **relevance**: ``retrieval_miss`` (the evidence exists and is permitted, but
  the search did not surface it), ``no_evidence`` (nothing permitted answers);
* **validity**: ``withdrawn``, ``superseded``, ``contested``, ``stale_lease``,
  ``malformed_assertion``;
* **authority**: ``untrusted`` (the source lacks standing for this use) and
  ``no_permission`` (this principal may not see or use it).

:func:`classify` maps every refusal code the gate, verifier, limits and
enforcer can return (``memory_fabric.reasons.REASONS``) to one diagnosis; a
code with no mapping raises, so the taxonomy cannot silently fall behind.

:class:`EvidenceAvailability` records, separately, whether the needed fact
exists, was retrieved, is currently authorized and actually answers. The
evaluator sees all four. The actor sees only what it may: ``no_permission``
and ``no_evidence`` are the same ``not_available`` to an actor, so a refusal
never discloses that a private source exists. The result is advisory: it is
not a certificate or a grant, and the action gate refuses it as one.

:func:`search_ladder` runs the evidence search as an ordered, budgeted ladder,
``exact -> lexical -> hybrid (only if qualified) -> abstain``, and records the
cost of every rung. Each rung is a caller-supplied search that already applies
the store's filters, so the ladder cannot widen what is visible, and its budget
is its own: it never draws on the episode's task budget.
"""

from __future__ import annotations

__stability__ = "experimental"

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Callable, Iterable, Mapping, Sequence


class Diagnosis(StrEnum):
    ANSWERABLE = "answerable"
    RETRIEVAL_MISS = "retrieval_miss"
    NO_EVIDENCE = "no_evidence"
    WITHDRAWN = "withdrawn"
    SUPERSEDED = "superseded"
    CONTESTED = "contested"
    UNTRUSTED = "untrusted"
    NO_PERMISSION = "no_permission"
    STALE_LEASE = "stale_lease"
    MALFORMED_ASSERTION = "malformed_assertion"


AXIS: Mapping[Diagnosis, str] = {
    Diagnosis.ANSWERABLE: "none",
    Diagnosis.RETRIEVAL_MISS: "relevance", Diagnosis.NO_EVIDENCE: "relevance",
    Diagnosis.WITHDRAWN: "validity", Diagnosis.SUPERSEDED: "validity",
    Diagnosis.CONTESTED: "validity", Diagnosis.STALE_LEASE: "validity",
    Diagnosis.MALFORMED_ASSERTION: "validity",
    Diagnosis.UNTRUSTED: "authority", Diagnosis.NO_PERMISSION: "authority",
}

# Codes that say "allowed" or describe an outcome rather than a refusal.
NOT_A_REFUSAL = frozenset({
    "ok", "allowed", "unprotected_tool", "executed", "already_executed", "failed", "timed_out",
    "uncertain", "refused", "active", "human_approval_required",
})
CODE_MAP: Mapping[str, Diagnosis] = {
    # relevance
    "evidence_off_target": Diagnosis.NO_EVIDENCE,
    "no_supporting_evidence": Diagnosis.NO_EVIDENCE,
    "evidence_not_found": Diagnosis.NO_EVIDENCE,
    "not_found": Diagnosis.NO_EVIDENCE,
    "dependency_not_found": Diagnosis.NO_EVIDENCE,
    "claim_evidence_not_supporting": Diagnosis.NO_EVIDENCE,
    "requirement_evidence_missing": Diagnosis.NO_EVIDENCE,
    "certificate_required": Diagnosis.NO_EVIDENCE,
    # validity
    "evidence_withdrawn": Diagnosis.WITHDRAWN, "dependency_withdrawn": Diagnosis.WITHDRAWN,
    "content_erased": Diagnosis.WITHDRAWN, "evidence_erased": Diagnosis.WITHDRAWN,
    "withdrawn_on_weak_evidence": Diagnosis.WITHDRAWN, "blocked_lifecycle": Diagnosis.WITHDRAWN,
    "evidence_not_usable": Diagnosis.WITHDRAWN,
    "evidence_version_moved": Diagnosis.SUPERSEDED, "version_moved": Diagnosis.SUPERSEDED,
    "dependency_version_moved": Diagnosis.SUPERSEDED, "integrity_moved": Diagnosis.SUPERSEDED,
    "evidence_outside_current_validity": Diagnosis.SUPERSEDED,
    "policy_changed": Diagnosis.SUPERSEDED,
    "contested": Diagnosis.CONTESTED, "claim_evidence_disputed": Diagnosis.CONTESTED,
    "evidence_not_fresh": Diagnosis.STALE_LEASE, "token_expired": Diagnosis.STALE_LEASE,
    "certificate_expired": Diagnosis.STALE_LEASE, "grant_expired": Diagnosis.STALE_LEASE,
    "malformed_certificate": Diagnosis.MALFORMED_ASSERTION,
    "unknown_certificate_version": Diagnosis.MALFORMED_ASSERTION,
    "unknown_required_check": Diagnosis.MALFORMED_ASSERTION,
    "certificate_too_large": Diagnosis.MALFORMED_ASSERTION,
    "payload_too_large": Diagnosis.MALFORMED_ASSERTION,
    "requirement_explanation_limit": Diagnosis.MALFORMED_ASSERTION,
    "idempotency_key_payload_mismatch": Diagnosis.MALFORMED_ASSERTION,
    "grant_binding_mismatch": Diagnosis.MALFORMED_ASSERTION,
    "grant_replayed": Diagnosis.MALFORMED_ASSERTION,
    "approval_invalid": Diagnosis.MALFORMED_ASSERTION,
    # authority
    "authority_insufficient": Diagnosis.UNTRUSTED, "evidence_suspicious": Diagnosis.UNTRUSTED,
    "evidence_provisional": Diagnosis.UNTRUSTED, "instruction_is_not_evidence": Diagnosis.UNTRUSTED,
    "insufficient_independent_support": Diagnosis.UNTRUSTED,
    "candidate_unvalidated": Diagnosis.UNTRUSTED,
    "unknown_tool": Diagnosis.NO_PERMISSION, "tool_not_granted": Diagnosis.NO_PERMISSION,
    "credential_invalid": Diagnosis.NO_PERMISSION,
    "execute_permission_missing": Diagnosis.NO_PERMISSION,
    "wrong_agent": Diagnosis.NO_PERMISSION, "wrong_store": Diagnosis.NO_PERMISSION,
    "wrong_tenant": Diagnosis.NO_PERMISSION, "not_visible": Diagnosis.NO_PERMISSION,
    "grant_required": Diagnosis.NO_PERMISSION, "grant_unknown": Diagnosis.NO_PERMISSION,
    "grant_revoked": Diagnosis.NO_PERMISSION,
    # resource limits: the request was not served, so nothing was established
    "memory_budget_exhausted": Diagnosis.NO_EVIDENCE,
    "write_quota_exhausted": Diagnosis.NO_EVIDENCE,
    "federation_budget_exhausted": Diagnosis.NO_EVIDENCE,
    "retry_required": Diagnosis.NO_EVIDENCE,
    "state_unavailable": Diagnosis.NO_EVIDENCE,
}
PRECEDENCE: tuple[Diagnosis, ...] = (
    Diagnosis.NO_PERMISSION, Diagnosis.MALFORMED_ASSERTION, Diagnosis.WITHDRAWN,
    Diagnosis.SUPERSEDED, Diagnosis.STALE_LEASE, Diagnosis.CONTESTED, Diagnosis.UNTRUSTED,
    Diagnosis.NO_EVIDENCE, Diagnosis.RETRIEVAL_MISS,
)
"""When several codes apply, authority is reported first, then validity, then relevance."""


def classify(reason_codes: Iterable[str]) -> Diagnosis:
    """One diagnosis for a set of refusal codes; ``answerable`` if none refuses."""
    found = set()
    for code in reason_codes:
        if code in NOT_A_REFUSAL:
            continue
        if code not in CODE_MAP:
            raise ValueError(f"no diagnosis for reason code {code!r}; extend CODE_MAP")
        found.add(CODE_MAP[code])
    for diagnosis in PRECEDENCE:
        if diagnosis in found:
            return diagnosis
    return Diagnosis.ANSWERABLE


@dataclass(frozen=True)
class EvidenceAvailability:
    """Exists / retrieved / authorized / answers, kept apart. Advisory, never authority."""

    exists: bool
    retrieved: bool
    authorized: bool
    answers: bool
    diagnosis: Diagnosis
    evidence: tuple[tuple[str, int], ...] = ()
    checked_at: int | None = None
    authorizes_effects: bool = field(default=False, init=False)

    def to_evaluator(self) -> dict[str, Any]:
        return {"exists": self.exists, "retrieved": self.retrieved, "authorized": self.authorized,
                "answers": self.answers, "diagnosis": self.diagnosis.value,
                "evidence": [list(pair) for pair in self.evidence],
                "checked_at": self.checked_at, "authorizes_effects": False}

    def to_actor(self) -> dict[str, Any]:
        """Only what the asking principal may know; a hidden source is just unavailable."""
        if not self.authorized or self.diagnosis in {Diagnosis.NO_PERMISSION,
                                                       Diagnosis.NO_EVIDENCE}:
            return {"diagnosis": "not_available", "retrieved": False, "evidence": [],
                    "authorizes_effects": False}
        return {"diagnosis": self.diagnosis.value, "retrieved": self.retrieved,
                "answers": self.answers, "evidence": [list(pair) for pair in self.evidence],
                "checked_at": self.checked_at, "authorizes_effects": False}


def availability(*, exists: bool, retrieved: bool, authorized: bool, answers: bool,
                 reason_codes: Iterable[str] = (), evidence: Sequence[tuple[str, int]] = (),
                 checked_at: int | None = None) -> EvidenceAvailability:
    """Build the availability record; the four facts decide relevance, the codes the rest."""
    diagnosis = classify(reason_codes)
    if diagnosis is Diagnosis.ANSWERABLE:
        if not authorized and exists:
            diagnosis = Diagnosis.NO_PERMISSION
        elif not exists:
            diagnosis = Diagnosis.NO_EVIDENCE
        elif not retrieved:
            diagnosis = Diagnosis.RETRIEVAL_MISS
        elif not answers:
            diagnosis = Diagnosis.NO_EVIDENCE
    return EvidenceAvailability(exists, retrieved, authorized, answers, diagnosis,
                                tuple(evidence), checked_at)


@dataclass(frozen=True)
class Rung:
    name: str
    search: Callable[[str], Sequence[Any]]
    qualified: bool = True
    cost: int = 1


@dataclass(frozen=True)
class LadderResult:
    rung: str | None
    results: tuple[Any, ...]
    costs: tuple[dict[str, Any], ...]
    abstained: bool
    spent: int


LADDER_ORDER = ("exact", "lexical", "hybrid")


def search_ladder(query: str, rungs: Sequence[Rung], *, budget: int) -> LadderResult:
    """Try rungs in the fixed order until one returns results or the budget runs out."""
    names = [rung.name for rung in rungs]
    if names != [name for name in LADDER_ORDER if name in names] or len(set(names)) != len(names):
        raise ValueError(f"rungs must follow {LADDER_ORDER} without repeats")
    spent, costs = 0, []
    for rung in rungs:
        if not rung.qualified:
            costs.append({"rung": rung.name, "skipped": "not_qualified", "cost": 0})
            continue
        if spent + rung.cost > budget:
            costs.append({"rung": rung.name, "skipped": "budget", "cost": 0})
            continue
        found = tuple(rung.search(query))
        spent += rung.cost
        costs.append({"rung": rung.name, "cost": rung.cost, "results": len(found)})
        if found:
            return LadderResult(rung.name, found, tuple(costs), False, spent)
    return LadderResult(None, (), tuple(costs), True, spent)

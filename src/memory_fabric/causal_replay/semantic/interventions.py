"""From a ranked proposal to an existing validated intervention, or a reasoned refusal (VEGA S06).

A model ranks *which* allowed intervention to investigate. It cannot execute
one, and it cannot write the replacement evidence. The closed vocabulary maps
onto the existing :func:`..intervention.create` operations; the two kinds with
no existing operation (``DUPLICATE``, ``REORDER_ALLOWED``) compile to
``UNSUPPORTED`` rather than to an improvised one (VEGA-CDM-061).

:func:`compile_proposal` refuses targets that are not readable and exposed in
the captured bundle (064), replacements that are not prevalidated local
fixtures (065), and anything past the budget (068). :func:`compile_batch` uses the
existing :func:`..intervention.compose`, which rejects contradictory or
ambiguous overlaps (069). Every proposal is recorded in a :class:`Ledger` whose
states keep *proposed*, *compiled*, *replayed* and *validated effect* distinct
(070), so an auditor can find every rejected or untested intervention.
"""

from __future__ import annotations

__stability__ = "experimental"

from dataclasses import dataclass, field
from typing import Mapping, Sequence

from ..intervention import InterventionBatch, Intervention, ReplacementFixture, compose, create
from ..types import BeliefReference, CDMError, digest_json
from .packets import PacketBundle

VOCABULARY = ("WITHHOLD", "REPLACE", "DELAY", "DUPLICATE", "REORDER_ALLOWED", "SWAP_POLICY", "NO_OP")
_OPERATION = {"WITHHOLD": "suppress", "REPLACE": "replace", "DELAY": "delay",
              "SWAP_POLICY": "swap_policy", "NO_OP": "noop"}
LEDGER_STATES = ("PROPOSED", "REJECTED", "UNSUPPORTED", "COMPILED", "REPLAYED",
                 "VALIDATED_EFFECT", "NO_EFFECT_CERTIFIED", "NOT_REPLAYED")
EXPECTED_CHANGES = ("decision_flip", "confidence_shift", "none_expected", "unknown")


@dataclass(frozen=True)
class InterventionProposal:
    kind: str
    target_ref: str | None
    reason_code: str
    receipt_digest: str | None
    expected_change: str = "unknown"
    fixture_id: str | None = None
    policy_id: str | None = None
    delay_until: int | None = None

    def __post_init__(self) -> None:
        if self.kind not in VOCABULARY:
            raise CDMError(f"intervention kind {self.kind!r} is outside the closed vocabulary")
        if self.expected_change not in EXPECTED_CHANGES:
            raise CDMError("unknown expected-change category")

    @property
    def proposal_id(self) -> str:
        return digest_json({"kind": self.kind, "target": self.target_ref, "reason": self.reason_code,
                            "fixture": self.fixture_id, "policy": self.policy_id,
                            "delay": self.delay_until})


@dataclass(frozen=True)
class Budget:
    max_candidates: int = 8
    max_depth: int = 1
    max_events: int = 1_000


@dataclass(frozen=True)
class Compiled:
    proposal: InterventionProposal
    status: str  # COMPILED | REJECTED | UNSUPPORTED
    intervention: Intervention | None
    reason: str = ""


@dataclass
class Ledger:
    entries: dict[str, dict[str, object]] = field(default_factory=dict)

    def record(self, proposal: InterventionProposal, state: str, **detail: object) -> None:
        if state not in LEDGER_STATES:
            raise CDMError(f"unknown ledger state {state}")
        entry = self.entries.setdefault(proposal.proposal_id, {
            "kind": proposal.kind, "target": proposal.target_ref, "history": []})
        history = entry["history"]
        assert isinstance(history, list)
        history.append({"state": state, **detail})
        entry["state"] = state

    def by_state(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for entry in self.entries.values():
            out[str(entry["state"])] = out.get(str(entry["state"]), 0) + 1
        return out


def target_reference(bundle: PacketBundle, ref: str) -> BeliefReference | None:
    """The captured belief reference for a readable, exposed packet, or None."""
    for packet in bundle.packets:
        if packet.ref == ref:
            return BeliefReference(ref.replace("@", "-v"), packet.version, packet.tenant_id,
                                   packet.content_hash)
    return None


def compile_proposal(proposal: InterventionProposal, bundle: PacketBundle, *,
                     readable_refs: set[str],
                     fixtures: Mapping[str, ReplacementFixture] | None = None,
                     policies: frozenset[str] = frozenset(),
                     observation_ids: Mapping[str, str] | None = None) -> Compiled:
    """Compile one proposal through :func:`..intervention.create`, or say why not.

    ``observation_ids`` maps a packet ref to the observation id the replay trace
    uses for it; an evidence intervention needs one.
    """
    if proposal.kind not in _OPERATION:
        return Compiled(proposal, "UNSUPPORTED", None, f"{proposal.kind} has no validated operation")
    operation = _OPERATION[proposal.kind]
    if operation in ("noop", "swap_policy"):
        if proposal.target_ref is not None:
            return Compiled(proposal, "REJECTED", None, "this kind takes no evidence target")
        if operation == "swap_policy" and proposal.policy_id not in policies:
            return Compiled(proposal, "REJECTED", None, "policy is not registered")
        try:
            return Compiled(proposal, "COMPILED", create(None, operation, policy_id=proposal.policy_id))
        except CDMError as exc:
            return Compiled(proposal, "REJECTED", None, str(exc))
    ref = proposal.target_ref
    if ref is None or ref not in readable_refs:
        return Compiled(proposal, "REJECTED", None, "target is not readable to this principal now")
    captured = target_reference(bundle, ref)
    if captured is None:
        return Compiled(proposal, "REJECTED", None, "target was not exposed in the captured bundle")
    obs_id = (observation_ids or {}).get(ref)
    if obs_id is None:
        return Compiled(proposal, "REJECTED", None, "target has no observation in the replay trace")
    target = BeliefReference(obs_id, captured.version, captured.tenant_id, captured.digest)
    try:
        if operation == "replace":
            fixture = (fixtures or {}).get(proposal.fixture_id or "")
            if fixture is None:
                return Compiled(proposal, "REJECTED", None,
                                "replacement must be a prevalidated local fixture, not generated text")
            return Compiled(proposal, "COMPILED", create(target, "replace", replacement=fixture))
        if operation == "delay":
            return Compiled(proposal, "COMPILED", create(target, "delay", delay_until=proposal.delay_until))
        return Compiled(proposal, "COMPILED", create(target, operation))
    except CDMError as exc:
        return Compiled(proposal, "REJECTED", None, str(exc))


def compile_all(proposals: Sequence[InterventionProposal], bundle: PacketBundle, *,
                readable_refs: set[str], ledger: Ledger, budget: Budget = Budget(),
                **kwargs: object) -> list[Compiled]:
    out = []
    for index, proposal in enumerate(proposals):
        ledger.record(proposal, "PROPOSED", reason=proposal.reason_code)
        if index >= budget.max_candidates:
            ledger.record(proposal, "REJECTED", reason="BUDGET_EXCEEDED: candidate count")
            out.append(Compiled(proposal, "REJECTED", None, "BUDGET_EXCEEDED: candidate count"))
            continue
        compiled = compile_proposal(proposal, bundle, readable_refs=readable_refs, **kwargs)  # type: ignore[arg-type]
        ledger.record(proposal, compiled.status, reason=compiled.reason)
        out.append(compiled)
    return out


def compile_batch(compiled: Sequence[Compiled]) -> InterventionBatch:
    """One hypothetical run from several compiled interventions; contradictions are refused."""
    items = tuple(c.intervention for c in compiled if c.intervention is not None)
    return compose(items)


def controls(bundle: PacketBundle, irrelevant_refs: Sequence[str]) -> list[InterventionProposal]:
    """Negative controls every family must run: a no-op, and removal of irrelevant evidence (066)."""
    out = [InterventionProposal("NO_OP", None, "control:no_op", None, "none_expected")]
    out += [InterventionProposal("WITHHOLD", ref, "control:irrelevant_removal", None, "none_expected")
            for ref in irrelevant_refs]
    return out

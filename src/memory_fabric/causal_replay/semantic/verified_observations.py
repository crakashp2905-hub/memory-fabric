"""The verification boundary between evidence, model proposals and decisions (VEGA next W04).

A *finding* is what deterministic code can stand behind about one sensor and one
property: ``VERIFIED`` (a readable, typed, span-bound observation from current,
authorized evidence), ``DISPUTED`` (readable observations of the same sensor at the
same time that disagree), ``UNKNOWN`` (the sensor is mentioned but no quantity could be
read, the unit or identity is unclear, or the statement is hedged), or
``INAPPLICABLE`` (the evidence is about something else). Every finding names its
evidence references and, when not ``VERIFIED``, the next permitted recovery step
(``RE_RETRIEVE``, ``CHECK_SOURCE`` or ``ASK``) - never a silent ``no_action`` (W04-07).

A model proposal is a separate object. :func:`cross_check` compares it with the
finding and can only mark the *proposal* rejected or disputed; it never changes the
finding, never makes an ``UNKNOWN`` finding verified, and never lowers a verified
hazard (W04-01 to W04-04, W02-08). Sensors that disagree with each other are reported
side by side as ``CONTESTED`` by :func:`aggregate`, without choosing a winner (W04-06).
Present-day findings use only active, uncorrected versions; historical findings use
what was known at the time asked (W04-05).
"""

from __future__ import annotations

__stability__ = "experimental"

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .entities import Registry
from .observations import Predicate, TypedObservation, evaluate, extract, verify_span

FINDING_STATUSES = ("VERIFIED", "DISPUTED", "UNKNOWN", "INAPPLICABLE")
NEXT_STEPS = ("RE_RETRIEVE", "CHECK_SOURCE", "ASK")


@dataclass(frozen=True)
class Finding:
    sensor: str
    property: str
    status: str
    value: str  # TRUE | FALSE | UNKNOWN for the predicate
    evidence_refs: tuple[str, ...]
    observations: tuple[TypedObservation, ...]
    next_step: str | None
    reason: str
    time: str | None = None


@dataclass(frozen=True)
class ProposalCheck:
    sensor: str
    proposal: str  # TRUE | FALSE | UNDECIDED
    finding: str  # the finding's status and value, e.g. VERIFIED:TRUE
    outcome: str  # CONSISTENT | REJECTED_CONTRADICTS_VERIFIED | NOT_USED_UNVERIFIABLE | UNDECIDED
    receipt_digest: str | None


@dataclass
class Verification:
    findings: dict[str, Finding] = field(default_factory=dict)
    checks: list[ProposalCheck] = field(default_factory=list)

    def aggregate(self) -> str:
        """VERIFIED_ALL_TRUE / VERIFIED_ALL_FALSE / CONTESTED / INCOMPLETE across sensors."""
        values = {f.value for f in self.findings.values() if f.status == "VERIFIED"}
        if any(f.status != "VERIFIED" for f in self.findings.values()) or not self.findings:
            return "INCOMPLETE"
        if values == {"TRUE"}:
            return "VERIFIED_ALL_TRUE"
        if values == {"FALSE"}:
            return "VERIFIED_ALL_FALSE"
        return "CONTESTED"


def _present(packets: Sequence[Any], known_at: int | None) -> list[Any]:
    if known_at is None:
        return [p for p in packets if p.status in ("active", "candidate")]
    return [p for p in packets if p.known_at <= known_at and p.status != "retracted"]


def verify(packets: Sequence[Any], registry: Registry, predicate: Predicate, *,
           required: Sequence[str] = (), default_unit: str | None = "C",
           known_at: int | None = None) -> Verification:
    """Findings per sensor from authorized packets; ``required`` sensors are always reported."""
    out = Verification()
    per_sensor: dict[str, list[TypedObservation]] = {}
    mentioned: dict[str, list[str]] = {}
    for p in _present(packets, known_at):
        res = registry.resolve(p.visible_text)
        if res.canonical is None:
            if len(res.candidates) > 1:
                for cand in res.candidates:
                    mentioned.setdefault(cand, []).append(p.ref)
            continue
        mentioned.setdefault(res.canonical, []).append(p.ref)
        for one in extract(p.visible_text, property=predicate.property, default_unit=default_unit,
                           evidence_ref=p.ref, sensor=res.canonical):
            if one.readable and not verify_span(one, p.visible_text):
                continue  # a value that does not read back from the text is not evidence
            per_sensor.setdefault(res.canonical, []).append(one)
    for sensor in sorted(set(required) | set(mentioned)):
        obs = per_sensor.get(sensor, [])
        refs = tuple(sorted(set(mentioned.get(sensor, ()))))
        readable = [o for o in obs if o.readable]
        if not refs:
            out.findings[sensor] = Finding(sensor, predicate.property, "UNKNOWN", "UNKNOWN", (), (),
                                           "RE_RETRIEVE", "no current evidence about this sensor")
            continue
        if not readable:
            reason = obs[0].reason if obs else "the sensor is mentioned but no quantity could be read"
            out.findings[sensor] = Finding(sensor, predicate.property, "UNKNOWN", "UNKNOWN", refs, tuple(obs),
                                           "CHECK_SOURCE", reason)
            continue
        latest_time = max((o.time or "") for o in readable)
        current = [o for o in readable if (o.time or "") == latest_time]
        values = {evaluate(o, predicate) for o in current}
        if len(values) > 1 and values != {"UNKNOWN"}:
            out.findings[sensor] = Finding(sensor, predicate.property, "DISPUTED", "UNKNOWN", refs, tuple(current),
                                           "ASK", "readings of this sensor at one time disagree", latest_time or None)
        elif values == {"UNKNOWN"}:
            out.findings[sensor] = Finding(sensor, predicate.property, "UNKNOWN", "UNKNOWN", refs, tuple(current),
                                           "CHECK_SOURCE", "the reading straddles the threshold", latest_time or None)
        else:
            out.findings[sensor] = Finding(sensor, predicate.property, "VERIFIED", values.pop(), refs,
                                           tuple(current), None, "", latest_time or None)
    return out


def cross_check(verification: Verification, sensor: str, answer: Any, receipt: Mapping[str, Any] | None = None
                ) -> ProposalCheck:
    """Compare a model's hot/cold proposal with the finding; only the proposal can lose."""
    finding = verification.findings.get(sensor)
    proposal = "UNDECIDED"
    if answer is not None and getattr(answer, "decisive", False) and getattr(answer, "value", None) is not None:
        proposal = "TRUE" if float(answer.value) > 0.5 else "FALSE"
    digest = (receipt or {}).get("receipt_digest")
    if finding is None:
        check = ProposalCheck(sensor, proposal, "NONE", "NOT_USED_UNVERIFIABLE", digest)
    elif proposal == "UNDECIDED":
        check = ProposalCheck(sensor, proposal, f"{finding.status}:{finding.value}", "UNDECIDED", digest)
    elif finding.status != "VERIFIED":
        check = ProposalCheck(sensor, proposal, f"{finding.status}:{finding.value}", "NOT_USED_UNVERIFIABLE", digest)
    elif proposal == finding.value:
        check = ProposalCheck(sensor, proposal, f"VERIFIED:{finding.value}", "CONSISTENT", digest)
    else:
        check = ProposalCheck(sensor, proposal, f"VERIFIED:{finding.value}", "REJECTED_CONTRADICTS_VERIFIED", digest)
    verification.checks.append(check)
    return check

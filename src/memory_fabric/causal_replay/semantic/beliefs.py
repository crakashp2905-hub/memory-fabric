"""Belief snapshots: observed evidence, model proposals and update status kept apart (VEGA S05).

A :class:`BeliefSnapshot` has three separate parts (VEGA-CDM-051):

* ``observations`` - deterministic :class:`~..state.Observation` values the host
  mapped from packets (a reading above a threshold is ``True``). Each carries its
  packet's source root as ``origin``, so the existing updater folds copies of one
  origin into one observation (055).
* ``proposals`` - semantic likelihood proposals, a different type
  (:class:`LikelihoodProposal`), accepted only for variables the registered model
  declares as observational (053). They never enter the exact posterior.
* ``status`` - ``EXACT`` when the posterior is the registered enumerator's over
  complete inputs, ``APPROXIMATE`` when any proposal or truncated bundle shaped it,
  ``NON_REPLAYABLE`` when inputs are missing (057).

:func:`reconstruct` rebuilds the belief as it was *known* at a time, so evidence
recorded later never leaks backwards, while late-arriving evidence about an
earlier valid time is included once it is known (056). A hypothetical
continuation needs a registered simulator; without one the result is
``UNDEFINED_CONTINUATION`` (058). The snapshot digest is taken over packets,
which refuse sealed evaluator fields, so outcome labels cannot shape it (060).
"""

from __future__ import annotations

__stability__ = "experimental"

from dataclasses import dataclass
from typing import Callable, Mapping, Sequence

from ..bayes import BinaryNode, enumerate_posterior, marginal
from ..state import Observation, update
from ..types import digest_json
from .advice import Answer
from .packets import PacketBundle, SemanticEvidencePacket

Mapper = Callable[[SemanticEvidencePacket], Sequence[tuple[str, bool]]]


class BeliefError(ValueError):
    pass


@dataclass(frozen=True)
class LikelihoodProposal:
    variable: str
    p_true: float
    receipt_digest: str | None
    tier: str = "HYPOTHETICAL_EFFECT"


@dataclass(frozen=True)
class BeliefSnapshot:
    known_at: int
    observations: tuple[Observation, ...]
    posterior: Mapping[str, float]
    conflicts: tuple[str, ...]
    proposals: tuple[LikelihoodProposal, ...]
    status: str
    packet_digest: str

    @property
    def digest(self) -> str:
        return digest_json({"known_at": self.known_at, "posterior": dict(self.posterior),
                            "observations": [o.__dict__ for o in self.observations],
                            "packet_digest": self.packet_digest, "status": self.status})


def observations_from(packets: Sequence[SemanticEvidencePacket], mapper: Mapper
                      ) -> tuple[Observation, ...]:
    out = []
    for seq, packet in enumerate(packets):
        for variable, value in mapper(packet):
            out.append(Observation(f"{packet.ref}:{variable}", variable, value,
                                   packet.origin_root, packet.known_at * 1000 + seq))
    return tuple(out)


def propose_likelihood(variable: str, answer: Answer, declared: frozenset[str],
                       receipt_digest: str | None) -> LikelihoodProposal | None:
    """A boolean answer as a likelihood proposal, only for a declared observational variable."""
    if variable not in declared:
        raise BeliefError(f"{variable} is not a declared observational variable; "
                          "a model cannot invent a likelihood")
    if answer.kind != "boolean" or answer.status != "OK" or not isinstance(answer.value, float):
        return None
    return LikelihoodProposal(variable, answer.value, receipt_digest)


def reconstruct(bundle: PacketBundle, nodes: Sequence[BinaryNode], mapper: Mapper, *,
                known_at: int, proposals: Sequence[LikelihoodProposal] = ()) -> BeliefSnapshot:
    """The exact belief from what was known at ``known_at``; proposals are carried, not applied."""
    visible = [p for p in bundle.packets if p.known_at <= known_at and p.status != "retracted"]
    observations = observations_from(visible, mapper)
    state = update(tuple(nodes), observations)
    status = "EXACT"
    if bundle.status == "TRUNCATED_NOT_VALIDATED" or proposals:
        status = "APPROXIMATE"
    if not visible:
        status = "NON_REPLAYABLE"
    seen = PacketBundle(tuple(visible), bundle.status, bundle.dropped, bundle.limits)
    return BeliefSnapshot(known_at, state.observations, dict(state.posterior),
                          tuple(state.conflict_variables), tuple(proposals), status, seen.digest)


def exact_oracle(nodes: Sequence[BinaryNode], evidence: Mapping[str, bool]) -> dict[str, float]:
    """The registered enumerator, called directly: the comparator for any assisted belief (052)."""
    distribution = enumerate_posterior(nodes, dict(evidence))
    return {n.name: marginal(distribution, n.name) for n in nodes}


def continue_hypothetically(snapshot: BeliefSnapshot, action: str,
                            simulators: Mapping[str, object]) -> str:
    """What an action would have observed: only a registered simulator may say (058)."""
    if action not in simulators:
        return "UNDEFINED_CONTINUATION"
    return "REGISTERED_SIMULATOR"

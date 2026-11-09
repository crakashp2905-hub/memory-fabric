"""Independent first-party verification for deterministic replay traces."""

from __future__ import annotations

__stability__ = "experimental"

import itertools
import math
from dataclasses import dataclass
from typing import Mapping

from .bayes import BinaryNode
from .executor import ReplayExecution
from .policy import ThresholdPolicy
from .replay import DeterministicSimulator
from .state import Observation, update as canonical_update
from .types import ReplayStatus, digest_json


@dataclass(frozen=True)
class VerificationResult:
    verified: bool
    code: str
    checked_steps: int
    recomputed_final_fingerprint: str | None


@dataclass(frozen=True)
class AttributionVerification:
    verified: bool
    code: str
    players_checked: int
    recomputed_values: tuple[tuple[str, float], ...]


@dataclass(frozen=True)
class MinimalityVerification:
    verified: bool
    code: str
    claim: str
    checked_subsets: int
    proof_digest: str | None


def verify_minimality_proof(players: tuple[str, ...], *,
                            coalition_proposals: Mapping[tuple[str, ...], str | None],
                            sufficient_subset: tuple[str, ...],
                            target_proposal: str,
                            claim: str) -> MinimalityVerification:
    """Verify sufficiency/minimality from a complete, sealed exhaustive result table.

    This verifies the supplied deterministic table only; it does not establish
    that an external simulator generated the table honestly. Callers must bind
    its digest to the replay certificate and use an independently verified
    replay as the table's provenance.
    """
    from .certificates import MinimalityClaim

    allowed = {MinimalityClaim.SUFFICIENT.value, MinimalityClaim.INCLUSION_MINIMAL.value,
               MinimalityClaim.CARDINALITY_MINIMUM.value}
    if (type(players) is not tuple or not players or len(players) > 10
            or len(set(players)) != len(players) or claim not in allowed
            or not isinstance(target_proposal, str) or not target_proposal
            or type(sufficient_subset) is not tuple
            or len(set(sufficient_subset)) != len(sufficient_subset)
            or not set(sufficient_subset) <= set(players)):
        return MinimalityVerification(False, "INVALID_PROOF_INPUT", claim, 0, None)
    ordered = tuple(sorted(players))
    expected = {tuple(group) for size in range(len(ordered) + 1)
                for group in itertools.combinations(ordered, size)}
    if set(coalition_proposals) != expected:
        return MinimalityVerification(False, "COALITION_TABLE_INCOMPLETE", claim,
                                      len(coalition_proposals), None)
    if any(value is not None and (not isinstance(value, str) or not value)
           for value in coalition_proposals.values()):
        return MinimalityVerification(False, "INVALID_PROPOSAL", claim,
                                      len(expected), None)
    subset = tuple(sorted(sufficient_subset))
    if coalition_proposals[subset] != target_proposal:
        return MinimalityVerification(False, "SUBSET_NOT_SUFFICIENT", claim,
                                      len(expected), None)
    if claim in {MinimalityClaim.INCLUSION_MINIMAL.value,
                 MinimalityClaim.CARDINALITY_MINIMUM.value}:
        for size in range(len(subset)):
            for candidate in itertools.combinations(subset, size):
                if coalition_proposals[candidate] == target_proposal:
                    return MinimalityVerification(False, "SMALLER_SUBSET_SUFFICIENT", claim,
                                                  len(expected), None)
    if claim == MinimalityClaim.CARDINALITY_MINIMUM.value:
        for size in range(len(subset)):
            for candidate in itertools.combinations(ordered, size):
                if coalition_proposals[candidate] == target_proposal:
                    return MinimalityVerification(False, "SMALLER_SUBSET_SUFFICIENT", claim,
                                                  len(expected), None)
    proof = {"schema": "cdm-minimality-proof-v1", "players": ordered,
             "coalition_proposals": [[list(key), coalition_proposals[key]]
                                     for key in sorted(expected, key=lambda item: (len(item), item))],
             "sufficient_subset": subset, "target_proposal": target_proposal,
             "claim": claim}
    return MinimalityVerification(True, "VERIFIED", claim, len(expected), digest_json(proof))


def verify_small_n_shapley(players: tuple[str, ...], *,
                           coalition_values: Mapping[tuple[str, ...], float],
                           claimed_values: Mapping[str, float],
                           tolerance: float = 1e-12) -> AttributionVerification:
    """Independently recompute exact Shapley values from a complete sealed table."""
    if (type(players) is not tuple or len(players) > 10 or not players
            or len(set(players)) != len(players)
            or not math.isfinite(tolerance) or tolerance < 0):
        return AttributionVerification(False, "INVALID_PLAYERS", 0, ())
    ordered = tuple(sorted(players))
    expected_keys = {tuple(sorted(subset)) for size in range(len(players) + 1)
                     for subset in itertools.combinations(ordered, size)}
    if set(coalition_values) != expected_keys or set(claimed_values) != set(players):
        return AttributionVerification(False, "COALITION_TABLE_INCOMPLETE", 0, ())
    if any(not math.isfinite(value) for value in coalition_values.values()):
        return AttributionVerification(False, "INVALID_COALITION_VALUE", 0, ())
    count = len(players)
    computed: dict[str, float] = {}
    for player in players:
        others = tuple(candidate for candidate in ordered if candidate != player)
        total = 0.0
        for size in range(count):
            denominator = count * math.comb(count - 1, size)
            for subset in itertools.combinations(others, size):
                before = tuple(sorted(subset))
                after = tuple(sorted((*subset, player)))
                total += (coalition_values[after] - coalition_values[before]) / denominator
        computed[player] = total
    if any(not math.isfinite(value) or abs(value - computed[player]) > tolerance
           for player, value in claimed_values.items()):
        return AttributionVerification(False, "SHAPLEY_VALUE_MISMATCH", count,
                                       tuple(sorted(computed.items())))
    gain = coalition_values[ordered] - coalition_values[()]
    if abs(math.fsum(computed.values()) - gain) > tolerance:
        return AttributionVerification(False, "EFFICIENCY_MISMATCH", count,
                                       tuple(sorted(computed.items())))
    return AttributionVerification(True, "VERIFIED", count, tuple(sorted(computed.items())))


def _reference_state(nodes: tuple[BinaryNode, ...], observations: tuple[Observation, ...],
                     updater_id: str, policy_id: str) -> tuple[dict[str, float], str]:
    admitted_by_origin: dict[tuple[str, str], Observation] = {}
    for item in sorted(observations, key=lambda value: (value.sequence, value.observation_id)):
        admitted_by_origin.setdefault((item.origin, item.variable), item)
    admitted = tuple(sorted(admitted_by_origin.values(),
                            key=lambda value: (value.sequence, value.observation_id)))
    observed: dict[str, bool] = {}
    conflicts: set[str] = set()
    for item in admitted:
        if item.variable in observed and observed[item.variable] != item.value:
            conflicts.add(item.variable)
        else:
            observed.setdefault(item.variable, item.value)
    for name in conflicts:
        observed.pop(name, None)
    names = tuple(node.name for node in nodes)
    weighted: list[tuple[dict[str, bool], float]] = []
    for bitset in itertools.product((False, True), repeat=len(names)):
        assignment = dict(zip(names, bitset))
        if any(assignment[key] != value for key, value in observed.items()):
            continue
        weight = 1.0
        for node in nodes:
            parent_bits = tuple(assignment[name] for name in node.parents)
            chance = node.probability_true[parent_bits]
            weight *= chance if assignment[node.name] else 1 - chance
        weighted.append((assignment, weight))
    normalizer = math.fsum(weight for _, weight in weighted)
    if normalizer <= 0 or not math.isfinite(normalizer):
        raise ValueError("reference verifier found impossible evidence")
    posterior = {name: min(1.0, max(0.0, math.fsum(weight for assignment, weight in weighted
                                 if assignment[name]) / normalizer)) for name in names}
    # Posterior computation above is independent. Fingerprints serialize the
    # canonical updater's exact float representation, so use it only for that
    # byte-level commitment after the independent posterior has been computed.
    fingerprint = canonical_update(nodes, tuple(observations), updater_id=updater_id,
                                   policy_id=policy_id).fingerprint
    return posterior, fingerprint


def _proposal(variable: str, posterior: dict[str, float], policy: ThresholdPolicy) -> tuple[str, str]:
    probability = posterior[variable]
    if probability >= policy.diagnose_above:
        scores = {"monitor": 0.05, "investigate": 0.15, "diagnose": 0.8}
    elif probability >= policy.investigate_above:
        scores = {"monitor": 0.1, "investigate": 0.8, "diagnose": 0.1}
    else:
        scores = {"monitor": 0.8, "investigate": 0.15, "diagnose": 0.05}
    total = math.fsum(scores.values())
    probabilities = {name: score / total for name, score in scores.items()}
    selected = max(probabilities, key=lambda name: probabilities[name])
    return selected, digest_json({"selected": selected, "probabilities": probabilities,
                                  "policy": policy.policy_id})


def verify_execution(observations: tuple[Observation, ...], *,
                     execution: ReplayExecution, simulator: DeterministicSimulator,
                     policy: ThresholdPolicy) -> VerificationResult:
    """Recompute all trace claims using an independently written enumerator."""
    if (type(execution) is not ReplayExecution or execution.status is not ReplayStatus.EXACT
            or not execution.complete or execution.real_actions_executed
            or execution.rng_applicability != "not_applicable_deterministic_engine"
            or type(simulator) is not DeterministicSimulator
            or type(policy) is not ThresholdPolicy):
        return VerificationResult(False, "TRACE_NOT_VERIFIABLE", 0, None)
    ordered = tuple(sorted(observations, key=lambda item: (item.sequence, item.observation_id)))
    if len({item.observation_id for item in ordered}) != len(ordered):
        return VerificationResult(False, "DUPLICATE_EVENT_ID", 0, None)
    if len(ordered) != len(execution.steps) or execution.consumed != len(ordered):
        return VerificationResult(False, "TRACE_LENGTH_MISMATCH", 0, None)
    prefix: list[Observation] = []
    for index, (observation, step) in enumerate(zip(ordered, execution.steps), start=1):
        prefix.append(observation)
        posterior, fingerprint = _reference_state(simulator.nodes, tuple(prefix),
            simulator.updater_id, policy.policy_id)
        proposal, proposal_digest = _proposal(policy.variable, posterior, policy)
        if (step.sequence != observation.sequence or step.observation_id != observation.observation_id
                or step.belief_fingerprint != fingerprint or step.proposal != proposal
                or step.proposal_digest != proposal_digest):
            return VerificationResult(False, "STEP_MISMATCH", index, fingerprint)
    posterior, final_fingerprint = _reference_state(simulator.nodes, tuple(prefix),
        simulator.updater_id, policy.policy_id)
    if execution.final_state.fingerprint != final_fingerprint:
        return VerificationResult(False, "FINAL_STATE_MISMATCH", len(ordered), final_fingerprint)
    if any(abs(execution.final_state.posterior[name] - value) > 1e-12
           for name, value in posterior.items()):
        return VerificationResult(False, "POSTERIOR_MISMATCH", len(ordered), final_fingerprint)
    return VerificationResult(True, "VERIFIED", len(ordered), final_fingerprint)

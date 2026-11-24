"""Paired factual / intervention replay with independent verification (VEGA S07).

:func:`evaluate` runs the factual trace and the intervened trace through the
existing deterministic executor under the same simulator and policy, then
checks **both** with the independently written verifier before reporting an
effect (VEGA-CDM-071, 072, 078). Outcomes are kept as separate fields
(073):

* ``policy_flip`` - the proposed action differs at the end;
* ``belief_divergence`` - the first step at which the belief fingerprints differ;
* ``terminal_improvement`` - not decidable here: only a world's independent
  grader can say whether a flip helped, so this module returns ``NOT_GRADED``.

If the factual replay does not verify, the result is ``NO_EFFECT_CERTIFIED`` -
never a zero effect. A model receipt cannot certify anything: the verifier
takes only observations, the execution and the registered simulator.

:func:`grouped_leave_one_out` removes evidence one *source root* at a time, so
copies of one origin are ablated together (074). :func:`paired_interval` gives
a mean paired difference with a percentile bootstrap clustered by world seed
(076).
"""

from __future__ import annotations

__stability__ = "experimental"

import random
from dataclasses import dataclass
from typing import Mapping, Sequence

from ..executor import execute, first_divergence
from ..intervention import Intervention
from ..policy import ThresholdPolicy
from ..replay import DeterministicSimulator, replay
from ..state import Observation
from ..types import ReplayStatus
from ..verifier import verify_execution


@dataclass(frozen=True)
class EffectResult:
    status: str  # VALIDATED_EFFECT | NO_EFFECT | NO_EFFECT_CERTIFIED | UNKNOWN
    policy_flip: bool | None
    belief_divergence: int | None
    factual_proposal: str | None
    counterfactual_proposal: str | None
    terminal_improvement: str
    reason: str
    certificate: str | None
    tier: str


def _proposal(execution) -> str | None:  # type: ignore[no-untyped-def]
    return execution.steps[-1].proposal if execution.steps else None


def evaluate(observations: tuple[Observation, ...], intervention: Intervention, *,
             simulator: DeterministicSimulator, policy: ThresholdPolicy,
             max_events: int = 1_000) -> EffectResult:
    factual = execute(observations, simulator=simulator, policy=policy, max_events=max_events)
    check = verify_execution(observations, execution=factual, simulator=simulator, policy=policy)
    if not check.verified:
        return EffectResult("NO_EFFECT_CERTIFIED", None, None, None, None, "NOT_GRADED",
                            f"factual replay did not verify: {check.code}", None, "OBSERVED_DEPENDENCE")
    hypothetical = replay(observations, intervention=intervention, simulator_id="registered",
                          simulators={"registered": simulator}, max_steps=max_events)
    if hypothetical.status is not ReplayStatus.EXACT or not hypothetical.complete:
        return EffectResult("UNKNOWN", None, None, _proposal(factual), None, "NOT_GRADED",
                            "the intervened world is not replayable under registered assumptions",
                            None, "HYPOTHETICAL_EFFECT")
    changed = tuple(sorted(hypothetical.state.observations,
                           key=lambda o: (o.sequence, o.observation_id)))
    counterfactual = execute(changed, simulator=DeterministicSimulator(
        simulator.nodes, simulator.updater_id, hypothetical.state.policy_id), policy=policy,
        max_events=max_events) if changed else None
    if counterfactual is None:
        return EffectResult("UNKNOWN", None, None, _proposal(factual), None, "NOT_GRADED",
                            "the intervention removed every observation", None, "HYPOTHETICAL_EFFECT")
    second = verify_execution(changed, execution=counterfactual, simulator=DeterministicSimulator(
        simulator.nodes, simulator.updater_id, hypothetical.state.policy_id), policy=policy)
    if not second.verified:
        return EffectResult("NO_EFFECT_CERTIFIED", None, None, _proposal(factual), None, "NOT_GRADED",
                            f"counterfactual replay did not verify: {second.code}", None,
                            "HYPOTHETICAL_EFFECT")
    flip = _proposal(factual) != _proposal(counterfactual)
    return EffectResult("VALIDATED_EFFECT" if flip else "NO_EFFECT", flip,
                        first_divergence(factual, counterfactual), _proposal(factual),
                        _proposal(counterfactual), "NOT_GRADED",
                        "both replays verified independently",
                        f"{check.recomputed_final_fingerprint}:{second.recomputed_final_fingerprint}", "VALIDATED_COUNTERFACTUAL")


def grouped_leave_one_out(observations: tuple[Observation, ...], *, simulator: DeterministicSimulator,
                          policy: ThresholdPolicy) -> dict[str, bool]:
    """For each source root: does removing all of its observations flip the proposal?"""
    base = _proposal(execute(observations, simulator=simulator, policy=policy))
    out = {}
    for root in sorted({o.origin for o in observations}):
        kept = tuple(o for o in observations if o.origin != root)
        out[root] = bool(kept) and _proposal(execute(kept, simulator=simulator, policy=policy)) != base
    return out


def paired_interval(differences: Mapping[int, Sequence[float]], *, draws: int = 2_000,
                    seed: int = 0, level: float = 0.95) -> dict[str, object]:
    """Mean paired difference with a cluster bootstrap over world seeds (VEGA-CDM-076)."""
    clusters = [list(v) for _, v in sorted(differences.items()) if v]
    if len(clusters) < 2:
        return {"mean": None, "interval": None, "clusters": len(clusters),
                "status": "NOT_ASSESSABLE: fewer than two clusters"}
    rng = random.Random(seed)
    flat = [x for c in clusters for x in c]
    means = []
    for _ in range(draws):
        sample = [x for _ in clusters for x in clusters[rng.randrange(len(clusters))]]
        means.append(sum(sample) / len(sample))
    means.sort()
    lo, hi = means[int((1 - level) / 2 * draws)], means[int((1 + level) / 2 * draws) - 1]
    return {"mean": round(sum(flat) / len(flat), 4), "interval": [round(lo, 4), round(hi, 4)],
            "clusters": len(clusters), "status": "ESTIMATED", "unit": "world seed cluster"}

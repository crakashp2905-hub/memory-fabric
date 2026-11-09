"""Small deterministic battery diagnostic demonstrator (synthetic only)."""

from __future__ import annotations

import argparse
import json
import math

from memory_fabric.causal_replay.bayes import BinaryNode
from memory_fabric.causal_replay.policy import ThresholdPolicy
from memory_fabric.causal_replay.state import Observation, update


def independent_oracle(nodes: tuple[BinaryNode, ...], observed: dict[str, bool],
                       query: str) -> float:
    """Separate recursive factor-product implementation for the demonstrator."""
    names = tuple(node.name for node in nodes)
    factors = {node.name: node for node in nodes}
    numerator: list[float] = []
    denominator: list[float] = []

    def visit(index: int, assignment: dict[str, bool], weight: float) -> None:
        if index == len(names):
            denominator.append(weight)
            if assignment[query]:
                numerator.append(weight)
            return
        name = names[index]
        values: tuple[bool, ...] = ((observed[name],) if name in observed
                                    else (False, True))
        node = factors[name]
        for value in values:
            p_true = node.probability_true[tuple(assignment[parent] for parent in node.parents)]
            assignment[name] = value
            visit(index + 1, assignment, weight * (p_true if value else 1 - p_true))
            del assignment[name]

    visit(0, {}, 1.0)
    total = math.fsum(denominator)
    if total <= 0:
        raise ValueError("oracle received impossible evidence")
    return math.fsum(numerator) / total


def run(seed: int = 20261108) -> dict[str, object]:
    """Run a frozen three-observation illustrative world; seed is recorded, not used globally."""
    if type(seed) is not int:
        raise ValueError("seed must be an integer")
    # Nodes: overheating is a world state; two sensor outcomes have explicit CPTs.
    graph = (
        BinaryNode("cooling_failure", (), {(): 0.08}),
        BinaryNode("overheating", ("cooling_failure",), {(False,): 0.12, (True,): 0.78}),
        BinaryNode("sensor_a_biased", (), {(): 0.10}),
        BinaryNode("sensor_a_high", ("overheating", "sensor_a_biased"),
                   {(False, False): 0.08, (False, True): 0.75,
                    (True, False): 0.90, (True, True): 0.95}),
        BinaryNode("sensor_b_high", ("overheating",), {(False,): 0.05, (True,): 0.92}),
    )
    events = (
        Observation("E1", "sensor_a_high", True, "sensor-A", 1),
        Observation("E2", "sensor_a_biased", True, "calibration-team", 2),
        Observation("E3", "sensor_b_high", True, "sensor-B", 3),
    )
    policy = ThresholdPolicy("overheating")
    stages = []
    for i, label in enumerate(("10:00", "10:15", "10:30"), start=1):
        current = events[:i]
        state = update(graph, current, policy_id=policy.policy_id)
        proposal = policy.propose(state)
        # Independent test oracle path: direct factor enumeration, separate API.
        observed = {o.variable: o.value for o in current}
        oracle = independent_oracle(graph, observed, "overheating")
        if abs(state.posterior["overheating"] - oracle) > 1e-12:
            raise AssertionError("candidate posterior disagrees with independent oracle")
        stages.append({"time": label, "posterior": state.posterior["overheating"],
                       "oracle": oracle, "proposal": proposal.selected,
                       "fingerprint": state.fingerprint})
    factual = update(graph, events, policy_id=policy.policy_id)
    suppressed = update(graph, (events[0], events[2]), policy_id=policy.policy_id)
    return {"schema": "cdm-battery-demo-v1", "seed": seed,
            "world": "generated illustrative battery sensors; not physical validation",
            "stages": stages,
            "counterfactual": {"intervention": "suppress E2 in disposable input",
                "factual_probability": factual.posterior["overheating"],
                "counterfactual_probability": suppressed.posterior["overheating"],
                "factual_proposal": policy.propose(factual).selected,
                "counterfactual_proposal": policy.propose(suppressed).selected,
                "real_actions_executed": False}}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=20261108)
    args = parser.parse_args()
    print(json.dumps(run(args.seed), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

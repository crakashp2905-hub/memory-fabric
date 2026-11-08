"""Enumerate exact decision worlds and compare IPS with oracle causal effects."""

from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path
from typing import Callable

from memory_fabric import events as ev
from memory_fabric.estimators import IPSEstimator
from memory_fabric.eventlog import EventLog
from memory_fabric.projections import Projection

ROOT = Path(__file__).resolve().parents[1]
TOLERANCE = 1e-12
World = tuple[str, tuple[str, ...], Callable[[frozenset[str]], float]]


def worlds() -> tuple[World, ...]:
    return (
        ("complementary", ("a", "b", "x", "y"),
         lambda included: float({"a", "b"} <= included)),
        ("redundant", ("a", "b", "x", "y"),
         lambda included: float(bool({"a", "b"} & included))),
        ("harmful", ("harmful", "x", "y", "z"),
         lambda included: float("harmful" not in included)),
        ("irrelevant", ("useful", "irrelevant", "x", "y"),
         lambda included: float("useful" in included)),
    )


def exact_effect(
    memories: tuple[str, ...], outcome: Callable[[frozenset[str]], float], memory: str
) -> float:
    others = tuple(candidate for candidate in memories if candidate != memory)
    differences = []
    for flags in itertools.product((False, True), repeat=len(others)):
        background = frozenset(m for m, included in zip(others, flags) if included)
        differences.append(outcome(background | {memory}) - outcome(background))
    return sum(differences) / len(differences)


def run() -> dict[str, object]:
    result_worlds: list[dict[str, object]] = []
    for world_name, memories, outcome in worlds():
        log = EventLog(":memory:")
        projection = Projection()

        def emit(event: object) -> None:
            for stored in log.append_many([event]):  # type: ignore[list-item]
                projection.apply(stored)

        subsets = [
            frozenset(memory for memory, included in zip(memories, flags) if included)
            for flags in itertools.product((False, True), repeat=len(memories))
        ]
        for index, included in enumerate(subsets):
            episode_id = f"{world_name}-{index:02d}"
            emit(ev.episode_started(
                ts=index, agent_id="oracle-benchmark", episode_id=episode_id,
                task_id=world_name, context={"world": world_name}, seed=index,
            ))
            for memory in memories:
                emit(ev.exposure_decided(
                    ts=index, agent_id="oracle-benchmark", episode_id=episode_id,
                    memory_id=memory, version=1, exposed=memory in included,
                    propensity=0.5, policy_id="enumerated-uniform-subsets-v1",
                ))
            emit(ev.outcome_recorded(
                ts=index, episode_id=episode_id, outcome=outcome(included),
                verifier_id="deterministic-world-oracle-v1",
            ))

        estimator = IPSEstimator(min_n_eff=2.0, clip_weight=20.0)
        estimator.fit(projection.state)
        effects = []
        for memory in memories:
            oracle = exact_effect(memories, outcome, memory)
            estimate = estimator.estimate(memory, context={"world": world_name})
            error = estimate.mean - oracle
            effects.append({
                "memory_id": memory,
                "oracle_average_inclusion_effect": oracle,
                "ips_estimate": estimate.mean,
                "absolute_error": abs(error),
                "passed": abs(error) <= TOLERANCE,
                "contrastive": estimate.contrastive,
                "n_eff": estimate.n_eff,
            })
        result_worlds.append({
            "world": world_name,
            "memory_count": len(memories),
            "enumerated_subsets": len(subsets),
            "effects": effects,
            "passed": all(bool(row["passed"]) for row in effects),
        })
        log.close()

    all_passed = all(bool(world["passed"]) for world in result_worlds)
    return {
        "schema": "memory-fabric-n3-02-exact-oracle/1",
        "experiment": "uniform exhaustive subset inclusion",
        "estimand": "finite-world average paired inclusion effect over uniform backgrounds",
        "assignment_propensity": 0.5,
        "tolerance": TOLERANCE,
        "world_count": len(result_worlds),
        "total_enumerated_subsets": sum(int(w["enumerated_subsets"]) for w in result_worlds),
        "passed": all_passed,
        "worlds": result_worlds,
        "limitations": [
            "Deterministic synthetic worlds validate implementation against the registered estimand only.",
            "Uniform-background inclusion effects are not Shapley values or context-free memory value.",
            "No claim is made about real-world confounding, stochasticity, or agent adaptation.",
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    payload = run()
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(rendered, encoding="utf-8")
        print(f"wrote {arguments.output}")
    else:
        print(rendered, end="")
    raise SystemExit(0 if payload["passed"] else 1)

"""Check causal credit stability as irrelevant copied memories multiply."""

from __future__ import annotations

import argparse
import itertools
import json
import math
from collections.abc import Callable
from pathlib import Path

from memory_fabric import events as ev
from memory_fabric.estimators import IPSEstimator
from memory_fabric.eventlog import EventLog
from memory_fabric.model import Memory, MemoryType, Provenance
from memory_fabric.projections import Projection

COPY_COUNTS = (0, 1, 2, 4, 8)
TOLERANCE = 1e-12


def oracle_outcome(included: frozenset[str]) -> float:
    return float("useful" in included)


def _exact_effect(
    memories: tuple[str, ...], outcome: Callable[[frozenset[str]], float], memory: str
) -> float:
    others = tuple(candidate for candidate in memories if candidate != memory)
    contrasts = []
    for flags in itertools.product((False, True), repeat=len(others)):
        background = frozenset(candidate for candidate, included in zip(others, flags) if included)
        contrasts.append(outcome(background | {memory}) - outcome(background))
    return sum(contrasts) / len(contrasts)


def _exact_shapley(
    memories: tuple[str, ...], outcome: Callable[[frozenset[str]], float], memory: str
) -> float:
    n = len(memories)
    others = tuple(candidate for candidate in memories if candidate != memory)
    value = 0.0
    for flags in itertools.product((False, True), repeat=len(others)):
        background = frozenset(candidate for candidate, included in zip(others, flags) if included)
        size = len(background)
        weight = math.factorial(size) * math.factorial(n - size - 1) / math.factorial(n)
        value += weight * (outcome(background | {memory}) - outcome(background))
    return value


def _world(copy_count: int) -> tuple[tuple[str, ...], Projection]:
    memories = ("useful", "irrelevant-root", *(f"copy-{index:02d}" for index in range(copy_count)))
    log = EventLog(":memory:")
    projection = Projection()

    def emit(event: object) -> None:
        for stored in log.append_many([event]):  # type: ignore[list-item]
            projection.apply(stored)

    for index, memory_id in enumerate(memories):
        emit(ev.memory_created(
            ts=index,
            memory=Memory(
                id=memory_id,
                version=1,
                type=MemoryType.SEMANTIC,
                content=f"{memory_id} note",
                provenance=Provenance(created_by="n3-06-oracle"),
            ),
        ))
    for index, copy_id in enumerate(memories[2:], start=len(memories)):
        emit(ev.copy_recognised(
            ts=index, agent_id="n3-06-oracle", episode_id=None,
            memory_id=copy_id, original_memory_id="irrelevant-root", containment=1.0,
        ))

    for episode_index, flags in enumerate(itertools.product((False, True), repeat=len(memories))):
        included = frozenset(memory_id for memory_id, flag in zip(memories, flags) if flag)
        episode_id = f"copy-{copy_count}-subset-{episode_index:04d}"
        emit(ev.episode_started(
            ts=episode_index, agent_id="n3-06-oracle", episode_id=episode_id,
            task_id="irrelevant-copy-world", context={"copies": copy_count}, seed=episode_index,
        ))
        for memory_id in memories:
            emit(ev.exposure_decided(
                ts=episode_index, agent_id="n3-06-oracle", episode_id=episode_id,
                memory_id=memory_id, version=1, exposed=memory_id in included,
                propensity=0.5, policy_id="exhaustive-independent-inclusion-v1",
            ))
        emit(ev.outcome_recorded(
            ts=episode_index, episode_id=episode_id, outcome=oracle_outcome(included),
            verifier_id="copy-invariance-oracle-v1",
        ))

    log.close()
    return memories, projection


def run() -> dict[str, object]:
    rows: list[dict[str, object]] = []
    for copy_count in COPY_COUNTS:
        memories, projection = _world(copy_count)
        estimator = IPSEstimator(min_n_eff=2.0)
        estimator.fit(projection.state)
        useful_oracle = _exact_effect(memories, oracle_outcome, "useful")
        useful_shapley = _exact_shapley(memories, oracle_outcome, "useful")
        useful_ips = estimator.estimate("useful").mean
        irrelevant_ids = ("irrelevant-root", *memories[2:])
        irrelevant_shapley = sum(
            _exact_shapley(memories, oracle_outcome, memory) for memory in irrelevant_ids
        )
        irrelevant_ips_values = [estimator.estimate(memory).mean for memory in irrelevant_ids]
        irrelevant_ips_total = sum(irrelevant_ips_values)
        rows.append({
            "irrelevant_copy_count": copy_count,
            "recognized_copy_count": len(projection.state.copy_of),
            "enumerated_subset_count": 2 ** len(memories),
            "memory_count": len(memories),
            "useful_exact_average_inclusion_effect": useful_oracle,
            "useful_exact_shapley": useful_shapley,
            "useful_ips_estimate": useful_ips,
            "irrelevant_group_exact_shapley_total": irrelevant_shapley,
            "irrelevant_group_ips_total": irrelevant_ips_total,
            "irrelevant_group_max_abs_ips": max(abs(value) for value in irrelevant_ips_values),
        })

    useful_values = [float(row["useful_ips_estimate"]) for row in rows]
    irrelevant_totals = [float(row["irrelevant_group_ips_total"]) for row in rows]
    result: dict[str, object] = {
        "schema": "memory-fabric-n3-06-copy-invariance/1",
        "copy_counts": list(COPY_COUNTS),
        "tolerance": TOLERANCE,
        "useful_credit_max_drift": max(useful_values) - min(useful_values),
        "irrelevant_credit_max_abs_total": max(abs(value) for value in irrelevant_totals),
        "useful_credit_stable": max(useful_values) - min(useful_values) <= TOLERANCE,
        "irrelevant_copy_credit_zero": max(abs(value) for value in irrelevant_totals) <= TOLERANCE,
        "worlds": rows,
        "limitations": [
            "All subsets are enumerated in deterministic synthetic worlds with recognized copy lineage.",
            "Unrecognized paraphrases and observational settings without overlap are not covered.",
            "The noncontrastive usage baseline is not causal credit and must not be summed across copies.",
        ],
    }
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run()
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(f"wrote {args.output}")
    else:
        print(rendered, end="")
    raise SystemExit(0 if result["useful_credit_stable"] and result["irrelevant_copy_credit_zero"] else 1)

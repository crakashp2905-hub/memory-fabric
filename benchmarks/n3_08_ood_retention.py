"""Transfer a source-trained causal retention score to two new task families."""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Any

from memory_fabric import events as ev
from memory_fabric.estimators import IPSEstimator, NaiveUsageEstimator
from memory_fabric.eventlog import EventLog
from memory_fabric.model import Memory, MemoryType, Provenance
from memory_fabric.projections import Projection
from experiments.stats import bootstrap_ci, mean

SEEDS = tuple(range(10))
MEMORIES_PER_KIND = 20
SOURCE_EPISODES_PER_MEMORY = 500
CALIBRATION_EPISODES_PER_MEMORY = 100
EVALUATION_EPISODES = 3_000
BUDGET = MEMORIES_PER_KIND
PROMOTION_MARGIN = 0.05
CONFIDENCE = 0.95

KINDS = ("legacy", "procedure")
FAMILIES: dict[str, dict[str, Any]] = {
    "supply_chain_dispatch": {
        "easy_success": 0.95,
        "hard_success": 0.35,
        "procedure_effect": 0.05,
        "legacy_effect": -0.05,
    },
    "incident_response": {
        "easy_success": 0.85,
        "hard_success": 0.25,
        "procedure_effect": 0.05,
        "legacy_effect": -0.05,
    },
}


def _memory(memory_id: str, kind: str) -> Memory:
    return Memory(
        id=memory_id,
        version=1,
        type=MemoryType.PROCEDURAL if kind == "procedure" else MemoryType.SEMANTIC,
        content=f"{kind} retention candidate {memory_id}",
        provenance=Provenance(created_by="n3-08-simulator"),
        context={"memory_kind": kind},
    )


def _projection_from_rows(rows: list[dict[str, Any]]) -> tuple[Projection, EventLog]:
    projection = Projection()
    log = EventLog(":memory:")
    memory_kinds = {row["memory_id"]: row["memory_kind"] for row in rows}
    events = [
        ev.memory_created(ts=0, memory=_memory(memory_id, kind))
        for memory_id, kind in sorted(memory_kinds.items())
    ]
    for index, row in enumerate(rows):
        episode_id = f"{row['family']}-{row['memory_id']}-{index:06d}"
        events.extend((
            ev.episode_started(
                ts=index + 1,
                agent_id="n3-08-policy",
                episode_id=episode_id,
                task_id=f"{row['family']}:{row['difficulty']}",
                context={"family": row["family"], "difficulty": row["difficulty"]},
                seed=row["seed"],
            ),
            ev.exposure_decided(
                ts=index + 1,
                agent_id="n3-08-policy",
                episode_id=episode_id,
                memory_id=row["memory_id"],
                version=1,
                exposed=row["exposed"],
                propensity=row["propensity"],
                policy_id=row["policy_id"],
            ),
            ev.outcome_recorded(
                ts=index + 1,
                episode_id=episode_id,
                outcome=row["outcome"],
                verifier_id="n3-08-synthetic-oracle-v1",
            ),
        ))
    for stored in log.append_many(events):
        projection.apply(stored)
    return projection, log


def _source_training(seed: int) -> tuple[dict[str, float], dict[str, float]]:
    rng = random.Random(10_000 + seed)
    rows: list[dict[str, Any]] = []
    memory_kinds: dict[str, str] = {}
    for kind in KINDS:
        for index in range(MEMORIES_PER_KIND):
            memory_id = f"source-{kind}-{index:02d}"
            memory_kinds[memory_id] = kind
            effect = 0.10 if kind == "procedure" else -0.10
            for episode in range(SOURCE_EPISODES_PER_MEMORY):
                easy = rng.random() < 0.5
                p_treated = 0.5
                treated = rng.random() < p_treated
                base = 0.75 if easy else 0.35
                p_success = base + (effect if treated else 0.0)
                rows.append({
                    "family": "source_rule_action",
                    "memory_id": memory_id,
                    "memory_kind": kind,
                    "difficulty": "easy" if easy else "hard",
                    "seed": seed,
                    "exposed": treated,
                    "propensity": p_treated,
                    "outcome": float(rng.random() < p_success),
                    "policy_id": "source-randomized-inclusion-v1",
                })

    projection, log = _projection_from_rows(rows)
    estimator = IPSEstimator(min_n_eff=2.0)
    estimator.fit(projection.state)
    by_kind: dict[str, list[float]] = defaultdict(list)
    for memory_id, kind in memory_kinds.items():
        by_kind[kind].append(estimator.estimate(memory_id).mean)
    learned_effects = {kind: mean(values) for kind, values in by_kind.items()}
    log.close()
    return learned_effects, {memory_id: memory_kinds[memory_id] for memory_id in memory_kinds}


def _target_calibration(family: str, seed: int) -> tuple[Projection, EventLog, dict[str, str]]:
    rng = random.Random(20_000 + seed * 101 + (0 if family == "supply_chain_dispatch" else 1))
    family_cfg = FAMILIES[family]
    rows: list[dict[str, Any]] = []
    memory_kinds: dict[str, str] = {}
    for kind in KINDS:
        for index in range(MEMORIES_PER_KIND):
            memory_id = f"{family}-{kind}-{index:02d}"
            memory_kinds[memory_id] = kind
            effect = float(family_cfg[f"{kind}_effect"])
            for episode in range(CALIBRATION_EPISODES_PER_MEMORY):
                easy = rng.random() < 0.5
                p_treated = (
                    0.5 if kind == "procedure"
                    else 0.9 if easy
                    else 0.1
                )
                treated = rng.random() < p_treated
                base = float(family_cfg["easy_success"] if easy else family_cfg["hard_success"])
                p_success = base + (effect if treated else 0.0)
                rows.append({
                    "family": family,
                    "memory_id": memory_id,
                    "memory_kind": kind,
                    "difficulty": "easy" if easy else "hard",
                    "seed": seed,
                    "exposed": treated,
                    "propensity": p_treated if treated else 1.0 - p_treated,
                    "outcome": float(rng.random() < p_success),
                    "policy_id": "difficulty-selected-calibration-v1",
                })
    projection, log = _projection_from_rows(rows)
    return projection, log, memory_kinds


def _select(scores: dict[str, float]) -> list[str]:
    return sorted(scores, key=lambda memory_id: (-scores[memory_id], memory_id))[:BUDGET]


def _evaluate(
    family: str, seed: int, selected: dict[str, list[str]], memory_kinds: dict[str, str]
) -> dict[str, float]:
    rng = random.Random(30_000 + seed * 103 + (0 if family == "supply_chain_dispatch" else 1))
    cfg = FAMILIES[family]
    successes = {policy: 0 for policy in selected}
    for _ in range(EVALUATION_EPISODES):
        easy = rng.random() < 0.5
        uniform = rng.random()
        slot = rng.randrange(BUDGET)
        base = float(cfg["easy_success"] if easy else cfg["hard_success"])
        for policy, memory_ids in selected.items():
            memory_id = memory_ids[slot]
            kind = memory_kinds[memory_id]
            effect = float(cfg[f"{kind}_effect"])
            successes[policy] += int(uniform < base + effect)
    return {policy: success / EVALUATION_EPISODES for policy, success in successes.items()}


def run() -> dict[str, object]:
    per_seed: dict[str, list[dict[str, Any]]] = {family: [] for family in FAMILIES}
    learned_effects_per_seed: list[dict[str, float]] = []
    selected_mix: dict[str, dict[str, dict[str, int]]] = {
        family: defaultdict(lambda: {kind: 0 for kind in KINDS}) for family in FAMILIES
    }

    for seed in SEEDS:
        learned_effects, _ = _source_training(seed)
        learned_effects_per_seed.append(learned_effects)
        for family in FAMILIES:
            target_projection, target_log, memory_kinds = _target_calibration(family, seed)
            naive = NaiveUsageEstimator()
            naive.fit(target_projection.state)
            naive_scores = {
                memory_id: naive.estimate(memory_id).mean for memory_id in memory_kinds
            }
            source_scores = {
                memory_id: learned_effects[kind] for memory_id, kind in memory_kinds.items()
            }
            oracle_scores = {
                memory_id: float(FAMILIES[family][f"{kind}_effect"])
                for memory_id, kind in memory_kinds.items()
            }
            chosen = {
                "source_causal_policy": _select(source_scores),
                "smoothed_success": _select(naive_scores),
                "oracle": _select(oracle_scores),
            }
            for policy, ids in chosen.items():
                for memory_id in ids:
                    selected_mix[family][policy][memory_kinds[memory_id]] += 1
            scores = _evaluate(family, seed, chosen, memory_kinds)
            per_seed[family].append({
                "seed": seed,
                "source_causal_policy": scores["source_causal_policy"],
                "smoothed_success": scores["smoothed_success"],
                "oracle": scores["oracle"],
                "paired_difference": scores["source_causal_policy"] - scores["smoothed_success"],
            })
            target_log.close()

    family_results: dict[str, dict[str, object]] = {}
    promotion_checks = []
    for family, rows in per_seed.items():
        differences = [row["paired_difference"] for row in rows]
        low, high = bootstrap_ci(differences, iterations=10_000, seed=90_000 + len(family))
        delta = mean(differences)
        gate = delta >= PROMOTION_MARGIN and low > 0.0
        promotion_checks.append(gate)
        family_results[family] = {
            "seed_count": len(rows),
            "causal_policy_mean_success": mean([row["source_causal_policy"] for row in rows]),
            "smoothed_success_mean_success": mean([row["smoothed_success"] for row in rows]),
            "oracle_mean_success": mean([row["oracle"] for row in rows]),
            "paired_difference_mean": delta,
            "paired_difference_ci_95": [low, high],
            "policy_memory_mix": dict(selected_mix[family]),
            "promotion_gate_passed": gate,
            "per_seed": rows,
        }
    return {
        "schema": "memory-fabric-n3-08-heldout-world-transfer/1",
        "source_family": "source_rule_action",
        "heldout_world_families": list(FAMILIES),
        "seeds": list(SEEDS),
        "source_episodes_per_memory": SOURCE_EPISODES_PER_MEMORY,
        "target_calibration_episodes_per_memory": CALIBRATION_EPISODES_PER_MEMORY,
        "heldout_evaluation_episodes_per_seed_family": EVALUATION_EPISODES,
        "memory_budget": BUDGET,
        "historical_h2_promotion_margin": PROMOTION_MARGIN,
        "learned_source_effects_by_seed": learned_effects_per_seed,
        "family_results": family_results,
        "promotion_gate_passed": all(promotion_checks),
        "limitations": [
            "Both new families preserve the preregistered procedure-versus-legacy causal-effect mapping; only task contexts and base-success generators shift.",
            "The source-trained policy uses coarse memory-kind features and known randomized source propensities; this is not a real-agent or model evaluation.",
            "The smoothed-success baseline uses target-family calibration outcomes; the source causal policy does not update on target outcomes.",
            "Results do not generalize to different feature semantics, hidden confounding, nonstationary effects, or field data.",
        ],
    }


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
    raise SystemExit(0 if result["promotion_gate_passed"] else 2)

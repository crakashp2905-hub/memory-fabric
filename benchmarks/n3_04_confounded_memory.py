"""Test propensity correction when an important memory is selected on easy tasks."""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from memory_fabric import events as ev
from memory_fabric.estimators import IPSEstimator
from memory_fabric.eventlog import EventLog
from memory_fabric.projections import Projection

EPISODES = 4_000
SEED = 3_404
TRUE_MEMORY_EFFECT = 0.15
EASY_BASELINE = 0.75
HARD_BASELINE = 0.25
P_EXPOSE_EASY = 0.9
P_EXPOSE_HARD = 0.1


def run() -> dict[str, object]:
    rng = random.Random(SEED)
    log = EventLog(":memory:")
    projection = Projection()
    exposed_outcomes: list[float] = []
    withheld_outcomes: list[float] = []
    exposed_easy = 0
    exposed_hard = 0
    withheld_easy = 0
    withheld_hard = 0

    def emit(event: object) -> None:
        for stored in log.append_many([event]):  # type: ignore[list-item]
            projection.apply(stored)

    for index in range(EPISODES):
        easy = index % 2 == 0
        p_expose = P_EXPOSE_EASY if easy else P_EXPOSE_HARD
        exposed = rng.random() < p_expose
        outcome = (EASY_BASELINE if easy else HARD_BASELINE) + (
            TRUE_MEMORY_EFFECT if exposed else 0.0
        )
        episode_id = f"n3-04-{index:04d}"
        emit(ev.episode_started(
            ts=index, agent_id="confounding-benchmark", episode_id=episode_id,
            task_id="easy" if easy else "hard",
            context={"difficulty": "easy" if easy else "hard"}, seed=index,
        ))
        emit(ev.exposure_decided(
            ts=index, agent_id="confounding-benchmark", episode_id=episode_id,
            memory_id="important-memory", version=1, exposed=exposed,
            propensity=p_expose if exposed else 1.0 - p_expose,
            policy_id="difficulty-selective-randomization-v1",
        ))
        emit(ev.outcome_recorded(
            ts=index, episode_id=episode_id, outcome=outcome,
            verifier_id="synthetic-outcome-oracle-v1",
        ))
        if exposed:
            exposed_outcomes.append(outcome)
            if easy:
                exposed_easy += 1
            else:
                exposed_hard += 1
        else:
            withheld_outcomes.append(outcome)
            if easy:
                withheld_easy += 1
            else:
                withheld_hard += 1

    estimator = IPSEstimator(min_n_eff=2.0)
    estimator.fit(projection.state)
    estimate = estimator.estimate("important-memory")
    naive_association = (
        sum(exposed_outcomes) / len(exposed_outcomes)
        - sum(withheld_outcomes) / len(withheld_outcomes)
    )
    result: dict[str, object] = {
        "schema": "memory-fabric-n3-04-confounded-credit/1",
        "seed": SEED,
        "episode_count": EPISODES,
        "true_average_treatment_effect": TRUE_MEMORY_EFFECT,
        "exposed_counts": {"easy": exposed_easy, "hard": exposed_hard},
        "withheld_counts": {"easy": withheld_easy, "hard": withheld_hard},
        "exposed_easy_rate": exposed_easy / (EPISODES // 2),
        "exposed_hard_rate": exposed_hard / (EPISODES // 2),
        "exposed_easy_fraction": exposed_easy / (exposed_easy + exposed_hard),
        "withheld_easy_fraction": withheld_easy / (withheld_easy + withheld_hard),
        "naive_unadjusted_exposed_minus_withheld": naive_association,
        "naive_bias": naive_association - TRUE_MEMORY_EFFECT,
        "ips_estimate": estimate.mean,
        "ips_ci_low": estimate.ci_low,
        "ips_ci_high": estimate.ci_high,
        "ips_absolute_error": abs(estimate.mean - TRUE_MEMORY_EFFECT),
        "ips_contrastive": estimate.contrastive,
        "ips_n_eff": estimate.n_eff,
        "naive_bias_requirement_passed": naive_association - TRUE_MEMORY_EFFECT >= 0.20,
        "ips_recovery_requirement_passed": abs(estimate.mean - TRUE_MEMORY_EFFECT) <= 0.04,
        "selection_enrichment_requirement_passed": exposed_easy / (exposed_easy + exposed_hard)
        > withheld_easy / (withheld_easy + withheld_hard),
        "limitations": [
            "Synthetic randomized assignment within known difficulty strata; hidden confounding and incorrect propensity logs are not tested.",
            "One memory and two task strata do not establish performance on real adaptive retrieval policies.",
        ],
    }
    log.close()
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
    passed = all(
        bool(result[key])
        for key in (
            "naive_bias_requirement_passed",
            "ips_recovery_requirement_passed",
            "selection_enrichment_requirement_passed",
            "ips_contrastive",
        )
    )
    raise SystemExit(0 if passed else 1)

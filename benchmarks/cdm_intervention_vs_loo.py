"""Five-seed R11 comparison of executed replay against fixed-continuation LOO."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from pathlib import Path
from typing import Any

PROTOCOL = "cdm-r11-intervention-vs-loo-v2"
PREREGISTRATION = "research/prereg/cdm-r11-intervention-vs-loo-v2.md"
SEEDS = (20261701, 20261702, 20261703, 20261704, 20261705)


def _world(seed: int) -> tuple[float, float, float]:
    rng = random.Random(seed)
    return (0.20 + rng.random() * 0.20,
            0.75 + rng.random() * 0.15,
            0.15 + rng.random() * 0.10)


def posterior(prior: float, sensitivity: float, false_positive: float,
              signal: bool) -> float:
    p_signal_fault = sensitivity if signal else 1.0 - sensitivity
    p_signal_clear = false_positive if signal else 1.0 - false_positive
    numerator = prior * p_signal_fault
    return numerator / (numerator + (1.0 - prior) * p_signal_clear)


def _propose(prior: float, sensitivity: float, false_positive: float,
             signal: bool) -> str:
    return "investigate" if posterior(prior, sensitivity, false_positive, signal) >= 0.50 \
        else "monitor"


def _transition(action: str) -> bool:
    """Frozen data-only R11 transition table; result is fault_signal."""
    transitions = {"investigate": False, "monitor": True}
    try:
        return transitions[action]
    except KeyError as exc:
        raise ValueError("unknown action in frozen R11 world") from exc


def _utility(action: str, evaluator_truth: bool) -> float:
    # This is the only function that consumes evaluator truth.
    if action == "investigate":
        return 0.0
    if action == "monitor":
        return -0.5 if evaluator_truth else 0.1
    raise ValueError("unknown proposal")


def run() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for seed in SEEDS:
        prior, sensitivity, false_positive = _world(seed)
        propose_args = (prior, sensitivity, false_positive)
        initial_proposal = _propose(*propose_args, signal=True)
        factual_signal = _transition(initial_proposal)
        factual_proposal = _propose(*propose_args, signal=factual_signal)

        # LOO suppresses the same initial alarm but holds factual continuation.
        loo_proposal = _propose(*propose_args, signal=factual_signal)
        # Executed intervention suppresses alarm, recomputes action, then replays
        # the action-dependent continuation from the frozen local world.
        intervened_initial_proposal = _propose(*propose_args, signal=False)
        replay_signal = _transition(intervened_initial_proposal)
        replay_proposal = _propose(*propose_args, signal=replay_signal)

        # Freeze every proposal before revealing the evaluator-only truth.
        proposals = {"factual": factual_proposal, "loo": loo_proposal,
                     "executed_replay": replay_proposal}
        evaluator_truth = True
        utilities = {arm: _utility(action, evaluator_truth)
                     for arm, action in proposals.items()}
        for arm in ("factual", "loo", "executed_replay"):
            rows.append({"seed": seed, "arm": arm, "prior_fault_probability": prior,
                "alarm_sensitivity": sensitivity, "alarm_false_positive": false_positive,
                "factual_initial_proposal": initial_proposal,
                "factual_continuation_signal": factual_signal,
                "proposal": proposals[arm],
                "counterfactual_proposal": None if arm == "factual" else proposals[arm],
                "continuation_signal": factual_signal if arm != "executed_replay"
                                       else replay_signal,
                "continuation_regenerated": arm == "executed_replay",
                "utility": utilities[arm],
                "utility_difference_vs_factual": utilities[arm] - utilities["factual"],
                "utility_difference_vs_loo": (None if arm != "executed_replay" else
                                               utilities[arm] - utilities["loo"])})

    factual_by_seed = {row["seed"]: row for row in rows if row["arm"] == "factual"}
    loo_by_seed = {row["seed"]: row for row in rows if row["arm"] == "loo"}
    replay_by_seed = {row["seed"]: row for row in rows if row["arm"] == "executed_replay"}
    paired = [{"seed": seed,
        "loo_proposal_changed_vs_factual": loo_by_seed[seed]["proposal"] !=
                                               factual_by_seed[seed]["proposal"],
        "replay_proposal_changed_vs_loo": replay_by_seed[seed]["proposal"] !=
                                              loo_by_seed[seed]["proposal"],
        "loo_utility_difference": loo_by_seed[seed]["utility_difference_vs_factual"],
        "replay_utility_difference": replay_by_seed[seed]["utility_difference_vs_factual"],
        "replay_utility_difference_vs_loo": replay_by_seed[seed]["utility_difference_vs_loo"]}
        for seed in SEEDS]
    replay_deltas = [item["replay_utility_difference_vs_loo"] for item in paired]
    mean_delta = math.fsum(replay_deltas) / len(replay_deltas)
    return {"schema": "cdm-intervention-vs-loo-v2", "protocol": PROTOCOL,
        "seeds": list(SEEDS), "rows": rows, "paired_results": paired,
        "summary": {"n": len(SEEDS), "mean_replay_minus_loo_utility": mean_delta,
            "normal_approx_95_interval": [mean_delta, mean_delta],
            "loo_proposal_changes": sum(item["loo_proposal_changed_vs_factual"]
                                         for item in paired),
            "replay_proposal_changes_vs_loo": sum(item["replay_proposal_changed_vs_loo"]
                                                   for item in paired)},
        "safety": {"truth_visible_to_proposer": False, "network_calls": 0,
            "model_calls": 0, "tool_calls": 0, "authority_changes": 0,
            "filesystem_reads_by_world": 0},
        "scope": "five registered seeded deterministic synthetic worlds",
        "limitations": ["Finite synthetic mechanism check; not a population efficacy estimate.",
            "No physical causal claim; simulator is a data-only transition table.",
            "Utility is stipulated by evaluator truth and not learned from data."]}


def _valid(result: dict[str, Any]) -> bool:
    if result["seeds"] != list(SEEDS) or len(result["rows"]) != 15:
        return False
    for item in result["paired_results"]:
        if (item["loo_proposal_changed_vs_factual"]
                or not item["replay_proposal_changed_vs_loo"]
                or item["loo_utility_difference"] != 0.0
                or item["replay_utility_difference"] != 0.5
                or item["replay_utility_difference_vs_loo"] != 0.5):
            return False
    return all(row["factual_initial_proposal"] == "investigate"
        and row["factual_continuation_signal"] is False
        and row["continuation_regenerated"] == (row["arm"] == "executed_replay")
        for row in result["rows"])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="research/results/cdm/intervention-vs-loo-r11")
    args = parser.parse_args()
    result = run()
    if not _valid(result):
        print("FAIL: preregistered R11 invariants did not hold")
        return 1
    root = Path(__file__).resolve().parents[1]
    output = Path(args.out)
    output.mkdir(parents=True, exist_ok=True)
    report_path = output / "report.json"
    report_bytes = (json.dumps(result, sort_keys=True, indent=2) + "\n").encode("utf-8")
    report_path.write_bytes(report_bytes)
    prereg = root / PREREGISTRATION
    config = {"protocol": PROTOCOL, "seeds": list(SEEDS),
              "generator": "random.Random(seed) on fixed prior/sensitivity/false-positive ranges",
              "arms": ["factual", "loo", "executed_replay"]}
    manifest = {"schema": "cdm-intervention-vs-loo-manifest-v2", "status": "PASS",
        "protocol": PROTOCOL,
        "protocol_sha256": hashlib.sha256(prereg.read_bytes()).hexdigest(),
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "report_sha256": hashlib.sha256(report_bytes).hexdigest(),
        "configuration_sha256": hashlib.sha256(json.dumps(config, sort_keys=True,
            separators=(",", ":")).encode("utf-8")).hexdigest(),
        "summary": result["summary"], "safety": result["safety"],
        "scope": result["scope"], "limitations": result["limitations"]}
    (output / "manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

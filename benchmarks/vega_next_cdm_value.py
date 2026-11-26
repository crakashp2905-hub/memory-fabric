"""Does selective counterfactual replay add measurable value? (VEGA next W08)

    python -m benchmarks.vega_next_cdm_value --seeds 40 --out research/results/vega-cdm/next/cdm/cdm-value.json

A shift plan decides one action for each of ``N`` packs from their typed readings. After
the plan, a correction arrives for some packs' readings (a transcription error). The
world's grader scores each pack's executed action against the corrected truth, so
replay has real headroom here: a plan that is not repaired executes stale decisions
(W08-08). Arms, all deterministic and model-free (W08-01):

``no_replay``       execute the plan as made (action-time verification would refuse the
                    stale ones; here they are counted as stale executions)
``full_replan``     recompute every decision after any correction
``dependence``      replay only decisions that relied on a corrected reading (dependence-first, W08-02)
``random_k`` / ``recency_k``  replay ``k`` decisions chosen at random / most recent, same budget as dependence
``oracle``          replay exactly the decisions whose outcome the correction changes

Reported per arm: safe completions, stale executions, replays, decision flips, flips that
improved the graded outcome, and net utility = safe completions - cost x replays (W08-06,
W08-10). A flip that does not improve the graded outcome earns nothing. Replays use the
existing replay executor and the independent verifier on each decision's observations
(W08-04, W08-05).
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from typing import Any, Sequence

from memory_fabric.causal_replay.bayes import BinaryNode
from memory_fabric.causal_replay.executor import execute
from memory_fabric.causal_replay.policy import ThresholdPolicy
from memory_fabric.causal_replay.replay import DeterministicSimulator
from memory_fabric.causal_replay.state import Observation
from memory_fabric.causal_replay.verifier import verify_execution

NODES = (BinaryNode("hot", (), {(): 0.2}), BinaryNode("reading_high", ("hot",), {(False,): 0.05, (True,): 0.95}))
SIM = DeterministicSimulator(NODES)
POLICY = ThresholdPolicy("hot", investigate_above=0.35, diagnose_above=0.6)
ACTION = {"diagnose": "cool_pack", "investigate": "abstain", "monitor": "no_action"}
ARMS = ("no_replay", "full_replan", "dependence", "random_k", "recency_k", "oracle")


def decide(high: bool, pack: str) -> tuple[str, bool]:
    """One pack's decision through the existing executor, checked by the independent verifier."""
    obs = (Observation(f"{pack}-reading", "reading_high", high, f"sensor/{pack}", 1),)
    execution = execute(obs, simulator=SIM, policy=POLICY)
    verified = verify_execution(obs, execution=execution, simulator=SIM, policy=POLICY).verified
    return ACTION.get(execution.steps[-1].proposal, "abstain"), verified


def world(seed: int, packs: int = 6, corrections: int = 1) -> dict[str, Any]:
    rng = random.Random(f"vega-next-cdm:{seed}")
    initial = {f"P{i}": rng.random() < 0.4 for i in range(packs)}
    corrected = dict(initial)
    changed = rng.sample(sorted(initial), corrections)
    for p in changed:
        corrected[p] = not corrected[p]
    order = {p: i for i, p in enumerate(sorted(initial))}
    return {"seed": seed, "initial": initial, "corrected": corrected, "changed": changed, "order": order}


def run_arm(arm: str, w: dict[str, Any], k: int, rng: random.Random) -> dict[str, Any]:
    plan = {p: decide(h, p)[0] for p, h in w["initial"].items()}
    truth = {p: ACTION["diagnose"] if h else ACTION["monitor"] for p, h in w["corrected"].items()}
    packs = sorted(plan)
    if arm == "no_replay":
        chosen: list[str] = []
    elif arm == "full_replan":
        chosen = packs
    elif arm == "dependence":
        chosen = list(w["changed"])
    elif arm == "random_k":
        chosen = rng.sample(packs, min(k, len(packs)))
    elif arm == "recency_k":
        chosen = sorted(packs, key=lambda p: -w["order"][p])[:k]
    else:  # oracle: exactly the decisions the correction changes
        chosen = [p for p in packs if decide(w["corrected"][p], p)[0] != plan[p]]
    final, flips, improving, verified = dict(plan), 0, 0, True
    for p in chosen:
        action, ok = decide(w["corrected"][p], p)
        verified = verified and ok
        if action != plan[p]:
            flips += 1
            improving += int(action == truth[p] and plan[p] != truth[p])
        final[p] = action
    safe = sum(final[p] == truth[p] for p in packs)
    stale = sum(final[p] != truth[p] for p in w["changed"])
    return {"arm": arm, "seed": w["seed"], "replays": len(chosen), "flips": flips, "improving_flips": improving,
            "safe_completions": safe, "stale_executions": stale, "packs": len(packs), "all_replays_verified": verified}


def run(seeds: Sequence[int], *, cost: float = 0.25, k: int = 1) -> dict[str, Any]:
    rng = random.Random(0)
    rows = [run_arm(arm, world(s), k, rng) for s in seeds for arm in ARMS]
    summary = {}
    for arm in ARMS:
        mine = [r for r in rows if r["arm"] == arm]
        safe, replays = sum(r["safe_completions"] for r in mine), sum(r["replays"] for r in mine)
        summary[arm] = {"tasks": len(mine), "decisions": sum(r["packs"] for r in mine), "safe_completions": safe,
                        "stale_executions": sum(r["stale_executions"] for r in mine), "replays": replays,
                        "flips": sum(r["flips"] for r in mine), "improving_flips": sum(r["improving_flips"] for r in mine),
                        "net_utility": round(safe - cost * replays, 2),
                        "all_replays_verified": all(r["all_replays_verified"] for r in mine)}
    best_fair = max(("full_replan", "random_k", "recency_k", "no_replay"), key=lambda a: summary[a]["net_utility"])
    gain = summary["dependence"]["net_utility"] - summary[best_fair]["net_utility"]
    return {"schema_id": "memory-fabric.vega-next-cdm-value.v1", "seeds": list(seeds), "replay_cost": cost,
            "budget_k": k, "summary": summary, "strongest_fair_comparator": best_fair,
            "dependence_minus_strongest": round(gain, 2),
            "oracle_headroom_over_no_replay": summary["oracle"]["safe_completions"]
            - summary["no_replay"]["safe_completions"],
            "verdict": ("POSITIVE_NET_UTILITY_SCRIPTED" if gain > 0 else "NONPOSITIVE"),
            "scope": "deterministic replay, scripted decisions; says nothing about a model-in-the-loop CDM",
            "rows": rows}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seeds", type=int, default=40)
    parser.add_argument("--seed-offset", type=int, default=0)
    parser.add_argument("--cost", type=float, default=0.25)
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    report = run(range(args.seed_offset, args.seed_offset + args.seeds), cost=args.cost)
    if args.out:
        import os
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(report, indent=1, sort_keys=True) + "\n")
    print(json.dumps({"summary": report["summary"], "strongest": report["strongest_fair_comparator"],
                      "gain": report["dependence_minus_strongest"], "verdict": report["verdict"]}, indent=1))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

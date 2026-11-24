"""Scripted factorial ablation and oracle-headroom analysis (W15-03, W15-05).

    python -m benchmarks.outcome_ablation --seeds 8 --out research/results/agent-outcomes/scripted-ablation-dev.json

**Factorial.** Two factors, each with two levels, every cell on the same tasks
with the same scripted team: *memory* (pooled with a retraction recheck, or
Memory Fabric with the action gate) and *recovery* (off or on). The pooled cell
without recovery is not a registered arm; it exists here only so the design is
complete. Main effects and the interaction are reported separately, per family,
so no factor is credited with another's gain. Correction propagation, source
independence and retrieval method are not separable factors in this harness;
they are listed as not run rather than folded into "memory".

**Headroom.** For each task: the oracle's best terminal, which arms reach it,
and whether the fair baseline A3 is already optimal. Tasks where A3 is optimal,
and tasks no arm can improve, are excluded from any improvement target.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Mapping, Sequence

from .outcome_arms import ARMS, FAMILIES, Arm, build_task, oracle_row, run_arm

SCHEMA_ID = "memory-fabric.scripted-factorial-ablation.v1"
CELLS = {
    ("pooled_recheck", False): Arm("F-pooled-norec", "pooled_recheck", False,
                                   "pooled + recheck, recovery off (design cell only)"),
    ("pooled_recheck", True): ARMS["A3"],
    ("governed", False): ARMS["A4"],
    ("governed", True): ARMS["A5"],
}
NOT_SEPARABLE = ("correction_propagation", "source_independence", "retrieval_method")


def _mean(values: Sequence[float]) -> float | None:
    return round(sum(values) / len(values), 4) if values else None


def effects(cell: Mapping[tuple[str, bool], float]) -> dict[str, float]:
    """2x2 main effects and interaction on a rate; positive favours the second level."""
    g0r0, g0r1 = cell[("pooled_recheck", False)], cell[("pooled_recheck", True)]
    g1r0, g1r1 = cell[("governed", False)], cell[("governed", True)]
    # ``+ 0.0`` turns a rounded -0.0 into 0.0 so a null effect never prints a sign.
    return {"governance_main": round(((g1r0 + g1r1) - (g0r0 + g0r1)) / 2, 4) + 0.0,
            "recovery_main": round(((g0r1 + g1r1) - (g0r0 + g1r0)) / 2, 4) + 0.0,
            "interaction": round((g1r1 - g1r0) - (g0r1 - g0r0), 4) + 0.0}


def factorial(seeds: int = 8, families: Sequence[str] = FAMILIES,
              metric: str = "safe_success") -> dict[str, Any]:
    rows = [{**run_arm(arm, build_task(family, seed)), "cell": [memory, recovery]}
            for (memory, recovery), arm in CELLS.items()
            for family in families for seed in range(seeds)]
    out: dict[str, Any] = {}
    for scope in ("overall", *families):
        mine = rows if scope == "overall" else [r for r in rows if r["family"] == scope]
        cell = {key: _mean([float(r[metric]) for r in mine
                            if (r["cell"][0], r["cell"][1]) == key]) or 0.0 for key in CELLS}
        out[scope] = {"cells": {f"{m}/{'recovery' if r else 'no-recovery'}": v
                                for (m, r), v in cell.items()},
                      **effects(cell)}
    return {"metric": metric, "by_scope": out, "rows": rows}


def headroom(seeds: int = 8, families: Sequence[str] = FAMILIES) -> dict[str, Any]:
    tasks = [build_task(family, seed) for family in families for seed in range(seeds)]
    per_task = []
    for task in tasks:
        best = oracle_row(task)["best_terminal"]
        reached = {arm_id: run_arm(arm, build_task(task.family, task.seed))["terminal_status"]
                   for arm_id, arm in ARMS.items()}
        optimal = sorted(a for a, status in reached.items() if best != "NONE" and status == best)
        per_task.append({"task_id": task.envelope.task_id, "family": task.family,
                         "seed": task.seed, "best_terminal": best, "arms_at_ceiling": optimal,
                         "a3_already_optimal": "A3" in optimal, "no_headroom": best == "NONE"})
    target = [t for t in per_task if not t["no_headroom"] and not t["a3_already_optimal"]]
    return {"tasks": len(per_task),
            "no_headroom": sum(t["no_headroom"] for t in per_task),
            "a3_already_optimal": sum(t["a3_already_optimal"] for t in per_task),
            "improvable_over_a3": len(target),
            "improvable_families": sorted({t["family"] for t in target}),
            "max_attainable_a5_minus_a3": round(len(target) / len(per_task), 4) if per_task else None,
            "per_task": per_task}


def _with_correction_at(seed: int, tick: int) -> Any:
    from .outcome_arms import Task, _envelope
    from .outcome_episode import build_correction_task

    base = build_task("public_correction", seed)
    world, _ = build_correction_task(seed, correction_tick=tick, family=f"timing{tick}")
    return Task(f"timing{tick}", seed, world,
                _envelope(world.spec.task_id, base.envelope.objective, base.envelope.limits),
                None, "COMPLETED")


def _without_marker(seed: int) -> Any:
    """The same correction world, but the correction no longer says it is one."""
    task = build_task("public_correction", seed)
    original = task.world.feed

    def feed(tick: int) -> list[dict[str, Any]]:
        out = []
        for item in original(tick):
            data = dict(item.get("data", {}))
            if data.get("status") == "correction":
                data["status"] = "update"
            out.append({**item, "data": data})
        return out

    setattr(task.world, "feed", feed)
    return task


def _with_distractors(seed: int, count: int) -> Any:
    """World difficulty: ``count`` readings from other instruments arrive with the real one."""
    import random as _random

    task = build_task("public_correction", seed)
    original, rng = task.world.feed, _random.Random(f"distract:{count}:{seed}")
    extra = [{"data": {"source": f"instrument-{chr(66 + i)}", "status": "initial",
                       "value": rng.randint(10, 60)},
              "event_id": f"reading-other-{i}", "kind": "observation", "revision_epoch": 0,
              "tick": 0} for i in range(count)]

    def feed(tick: int) -> list[dict[str, Any]]:
        return [*extra, *original(tick)]

    setattr(task.world, "feed", feed)
    return task


def _noisy_planner(rate: float, seed: int) -> Any:
    """A scripted planner that proposes a wrong value with probability ``rate`` (a proxy, not a model)."""
    import random as _random

    from memory_fabric.outcome_typed.observations import AgentStep

    from .outcome_episode import ScriptedTeam

    team, rng = ScriptedTeam(), _random.Random(f"noise:{rate}:{seed}")

    def decide(role: str, observation: Any) -> Any:
        step = team(role, observation)
        if role == "planner" and step.intent == "propose" and rng.random() < rate:
            arguments = json.loads(step.canonical_json())["arguments"]
            arguments["parameters"]["value"] += 1
            return AgentStep(step.task_id, step.actor_id, step.step_id, step.intent, arguments)
        return step

    return decide


def orthogonal(seeds: int = 8) -> dict[str, Any]:
    """Correction timing, evidence quality and planner accuracy, each varied alone (W22-06)."""
    from . import outcome_poisoning

    def rates(make_task: Any, decide: Any = None) -> dict[str, float]:
        out = {}
        for arm in ("A3", "A5"):
            rows = [run_arm(ARMS[arm], make_task(seed), decide(seed) if decide else None)
                    for seed in range(seeds)]
            out[arm] = round(sum(r["completed"] for r in rows) / len(rows), 4)
        out["A5_minus_A3"] = round(out["A5"] - out["A3"], 4) + 0.0
        return out

    timing = {str(tick): rates(lambda seed, t=tick: _with_correction_at(seed, t))
              for tick in (2, 3, 6, 12)}
    quality = {"marked_correction": rates(lambda seed: build_task("public_correction", seed)),
               "unmarked_correction": rates(_without_marker)}
    accuracy = {str(rate): rates(lambda seed: build_task("public_correction", seed),
                                 lambda seed, r=rate: _noisy_planner(r, seed))
                for rate in (0.0, 0.25, 0.5)}
    difficulty = {str(n): rates(lambda seed, k=n: _with_distractors(seed, k)) for n in (0, 2, 8)}
    stress = outcome_poisoning.run()["amplification_stress"]
    return {"metric": "completion", "factors": {
        "correction_timing_tick": timing, "evidence_quality": quality,
        "planner_error_rate_proxy": accuracy,
        "world_difficulty_distractor_instruments": difficulty,
        "source_independence_colluders": {str(r["colluders"]): {"roots": r["roots_false"],
                                                                "governed_fooled": r["governed_fooled"]}
                                          for r in stress}},
            "model_accuracy": "NOT_RUN: planner_error_rate_proxy is scripted noise, not a model",
            "confounds": "no prompts (scripted); opaque task ids; one factor varied at a time"}


def run(seeds: int = 8) -> dict[str, Any]:
    return {"schema_id": SCHEMA_ID, "population": "SCRIPTED_DEVELOPMENT",
            "promotion": "NOT_ASSESSED", "seeds": seeds, "families": list(FAMILIES),
            "factors": {"memory": ["pooled_recheck", "governed"], "recovery": [False, True]},
            "not_separable_in_this_harness": list(NOT_SEPARABLE),
            "cdm_ablation": "A6 is an arm in benchmarks.outcome_arms; its comparison with A5 is the cdm block of scripted-arms-dev.json",
            "factorial": factorial(seeds), "headroom": headroom(seeds),
            "orthogonal": orthogonal(seeds)}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seeds", type=int, default=8)
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    report = run(args.seeds)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(report, sort_keys=True, indent=1) + "\n")
    overall = report["factorial"]["by_scope"]["overall"]
    print(f"cells: {overall['cells']}")
    print(f"governance main {overall['governance_main']}, recovery main {overall['recovery_main']}, "
          f"interaction {overall['interaction']}")
    h = report["headroom"]
    print(f"headroom: {h['improvable_over_a3']}/{h['tasks']} tasks improvable over A3 "
          f"({h['improvable_families']}); {h['a3_already_optimal']} A3-optimal; "
          f"{h['no_headroom']} without headroom")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

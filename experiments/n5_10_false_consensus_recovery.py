"""Preregistered paired continuation test of H4b after false consensus."""
from __future__ import annotations

import hashlib
import json
import random
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from experiments import stats  # noqa: E402
from experiments.banditworld import (  # noqa: E402
    BAD, GOOD, BanditConfig, Beliefs, TOPOLOGIES, _binomial,
)

PREREG = ROOT / "research" / "prereg" / "n5-10-false-consensus-recovery-v1.md"
SEEDS = tuple(range(10_000, 11_000))
CHECKPOINT = 20
ARMS = (("complete", False), ("complete", True), ("ring", False), ("ring", True))


@dataclass(frozen=True)
class ForkOutcome:
    recovered: bool
    recovery_round: int | None
    bad_pulls: int
    total_pulls: int


def _clone_agents(agents: list[Beliefs]) -> list[Beliefs]:
    return [Beliefs(successes=list(item.successes), failures=list(item.failures))
            for item in agents]


def fork_seed(seed: int, config: BanditConfig | None = None) -> dict[str, Any] | None:
    """Return four paired continuations from one pre-treatment false consensus."""
    config = config or BanditConfig()
    rng = random.Random(seed)
    complete_neighbors = TOPOLOGIES["complete"](config.n_agents, rng)
    agents: list[Beliefs] = []
    for _ in range(config.n_agents):
        belief = Beliefs()
        belief.observe(BAD, _binomial(rng, config.known_observations, config.p_bad),
                       config.known_observations)
        seed_rate = rng.random()
        belief.observe(GOOD, _binomial(rng, config.prior_observations, seed_rate),
                       config.prior_observations)
        agents.append(belief)

    bad_pulls = total_pulls = 0
    for _round_index in range(CHECKPOINT + 1):
        results: list[list[tuple[int, int, int]]] = []
        for belief in agents:
            action = belief.believes()
            successes = _binomial(rng, config.pulls_per_round,
                                  (config.p_good, config.p_bad)[action])
            results.append([(action, successes, config.pulls_per_round)])
            total_pulls += config.pulls_per_round
            if action == BAD:
                bad_pulls += config.pulls_per_round
        for index, observations in enumerate(results):
            for action, successes, trials in observations:
                agents[index].observe(action, successes, trials)
                for neighbor in complete_neighbors[index]:
                    agents[neighbor].observe(action, successes, trials)

    if not all(belief.believes() == BAD for belief in agents):
        return None
    checkpoint_agents = _clone_agents(agents)
    rng_state = rng.getstate()
    topology_rng = random.Random(seed ^ 0x4E353130)
    neighbors_by_topology = {
        "complete": complete_neighbors,
        "ring": TOPOLOGIES["ring"](config.n_agents, topology_rng),
    }
    result: dict[str, Any] = {"seed": seed, "arms": {}}

    for topology, preserve in ARMS:
        branch_rng = random.Random()
        branch_rng.setstate(rng_state)
        branch = _clone_agents(checkpoint_agents)
        branch_bad = bad_pulls
        branch_total = total_pulls
        recovery_round = None
        neighbors = neighbors_by_topology[topology]
        for round_index in range(CHECKPOINT + 1, config.rounds):
            observations_by_agent: list[list[tuple[int, int, int]]] = []
            for belief in branch:
                believed = belief.believes()
                allocation = [(believed, config.pulls_per_round)]
                if preserve and belief.contested():
                    minority = BAD if believed == GOOD else GOOD
                    spend = int(round(config.preserve_share * config.pulls_per_round))
                    if spend:
                        allocation = [(believed, config.pulls_per_round - spend),
                                      (minority, spend)]
                observed: list[tuple[int, int, int]] = []
                for action, trials in allocation:
                    if trials <= 0:
                        continue
                    successes = _binomial(branch_rng, trials,
                                          (config.p_good, config.p_bad)[action])
                    observed.append((action, successes, trials))
                    branch_total += trials
                    if action == BAD:
                        branch_bad += trials
                observations_by_agent.append(observed)
            for index, observations in enumerate(observations_by_agent):
                for action, successes, trials in observations:
                    branch[index].observe(action, successes, trials)
                    for neighbor in neighbors[index]:
                        branch[neighbor].observe(action, successes, trials)
            if (recovery_round is None
                    and all(belief.believes() == GOOD for belief in branch)):
                recovery_round = round_index
        outcome = ForkOutcome(
            recovered=all(belief.believes() == GOOD for belief in branch),
            recovery_round=recovery_round, bad_pulls=branch_bad, total_pulls=branch_total,
        )
        result["arms"][f"{topology}_{'preserve' if preserve else 'collapse'}"] = {
            "recovered": outcome.recovered,
            "recovery_round": outcome.recovery_round,
            "bad_pull_fraction": outcome.bad_pulls / outcome.total_pulls,
        }
    return result


def analyze(rows: list[dict[str, Any]], minimum_eligible: int = 200) -> dict[str, Any]:
    if len(rows) < 2:
        raise ValueError(f"at least two eligible seeds are needed for interval estimates; observed {len(rows)}")
    contrasts = {
        "h1_complete_preserve_minus_complete_collapse":
            ("complete_preserve", "complete_collapse"),
        "h2_complete_preserve_minus_ring_collapse":
            ("complete_preserve", "ring_collapse"),
        "interaction": None,
    }
    result: dict[str, Any] = {"eligible_seeds": [row["seed"] for row in rows],
                              "eligible_count": len(rows),
                              "preregistered_minimum": minimum_eligible,
                              "preregistered_minimum_met": len(rows) >= minimum_eligible,
                              "arms": {}, "contrasts": {}}
    for arm, _ in ARMS:
        name = f"{arm}_{'preserve' if _ else 'collapse'}"
        recovered = [int(row["arms"][name]["recovered"]) for row in rows]
        times = [row["arms"][name]["recovery_round"] for row in rows]
        valid_times = [x for x in times if x is not None]
        result["arms"][name] = {
            "recovery_rate": sum(recovered) / len(recovered),
            "recovered_n": sum(recovered),
            "mean_recovery_round_among_recovered": (
                sum(valid_times) / len(valid_times) if valid_times else None),
            "mean_bad_pull_fraction": sum(row["arms"][name]["bad_pull_fraction"]
                                           for row in rows) / len(rows),
        }
    for contrast_name, contrast in contrasts.items():
        if contrast is None:
            diffs = [
                (int(row["arms"]["complete_preserve"]["recovered"])
                 - int(row["arms"]["complete_collapse"]["recovered"]))
                - (int(row["arms"]["ring_preserve"]["recovered"])
                   - int(row["arms"]["ring_collapse"]["recovered"]))
                for row in rows]
            low, high = stats.bootstrap_ci(diffs, iterations=10_000,
                                           confidence=0.95, seed=10510)
            result["contrasts"][contrast_name] = {
                "mean_difference_in_differences": stats.mean(diffs),
                "ci95": [low, high], "interpretation": "secondary_interaction",
            }
            continue
        treatment, control = contrast
        diffs = [int(row["arms"][treatment]["recovered"])
                 - int(row["arms"][control]["recovered"]) for row in rows]
        low, high = stats.bootstrap_ci(diffs, iterations=10_000,
                                       confidence=0.975, seed=10510)
        result["contrasts"][contrast_name] = {
            "treatment": treatment, "control": control,
            "mean_recovery_uplift": stats.mean(diffs), "ci97_5": [low, high],
        }
    h1 = result["contrasts"]["h1_complete_preserve_minus_complete_collapse"]
    h2 = result["contrasts"]["h2_complete_preserve_minus_ring_collapse"]
    result["verdict"] = (
        "SUPPORTED" if h1["mean_recovery_uplift"] >= 0.10 and h1["ci97_5"][0] > 0
        and h2["mean_recovery_uplift"] >= 0.10 and h2["ci97_5"][0] > 0 else "INCONCLUSIVE"
    )
    if (h1["ci97_5"][1] <= 0 or h2["ci97_5"][1] <= 0):
        result["verdict"] = "NOT_SUPPORTED"
    if not result["preregistered_minimum_met"]:
        result["verdict"] = "INCONCLUSIVE_UNDERPOWERED"
    return result


def run(seeds: tuple[int, ...] = SEEDS, config: BanditConfig | None = None,
        preregistration: Path = PREREG, minimum_eligible: int = 200) -> dict[str, Any]:
    started = time.perf_counter()
    rows = [row for seed in seeds if (row := fork_seed(seed, config)) is not None]
    analysis = analyze(rows, minimum_eligible)
    analysis.update({
        "schema": "memory-fabric-n5-10-false-consensus-recovery/1",
        "task_id": "N5-10", "acceptance_passed": True,
        "evidence_level": "SIMULATED",
        "preregistration": {
            "path": preregistration.relative_to(ROOT).as_posix(),
            "sha256": hashlib.sha256(preregistration.read_bytes()).hexdigest(),
            "git_commit": subprocess.run(["git", "log", "-1", "--format=%H", "--", str(preregistration.relative_to(ROOT))],
                                          cwd=ROOT, check=True, capture_output=True,
                                          text=True).stdout.strip(),
        },
        "source": {"commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                               check=True, capture_output=True,
                                               text=True).stdout.strip(),
                   "dirty_before_result_write": bool(subprocess.run(
                       ["git", "status", "--porcelain"], cwd=ROOT, check=True,
                       capture_output=True, text=True).stdout.strip()),
                   "experiment_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
        "protocol": {"seed_start": seeds[0], "seed_end_exclusive": seeds[-1] + 1,
                     "attempted_seeds": len(seeds), "minimum_eligible": minimum_eligible,
                     "checkpoint_round_index": CHECKPOINT,
                     "rounds": (config or BanditConfig()).rounds,
                     "eligible_rule": "all agents believe BAD at round index 20 under complete+collapse"},
        "runtime_seconds": round(time.perf_counter() - started, 3),
        "raw_paired_outcomes": rows,
        "limitations": [
            "This is a synthetic bandit mechanism test using the existing H4 simulator, not language-model agents or production memory behavior.",
            "Eligibility is conditional on false consensus under the pre-treatment complete+collapse path; results do not estimate population-wide prevention of false consensus.",
            "The intervention tests the same H4b posterior-overlap retesting rule; no independent semantic hypothesis detector is modeled.",
        ],
    })
    return analysis


def write_result(report: dict[str, Any]) -> None:
    suffix = "-followup" if "followup" in report["preregistration"]["path"] else ""
    out = ROOT / "research" / "results" / f"n5-10{suffix}-false-consensus-recovery.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    lines = ["# N5-10 false-consensus recovery experiment", "",
             f"Preregistration: [`{report['preregistration']['path']}`](../prereg/{Path(report['preregistration']['path']).name}).",
             f"Verdict: **{report['verdict']}**. Eligible paired false-consensus states: **{report['eligible_count']}** of {report['protocol']['attempted_seeds']} attempted seeds (preregistered minimum {report['preregistered_minimum']} met: `{report['preregistered_minimum_met']}`).", "",
             "| post-checkpoint arm | recovery rate | mean recovery round among recovered | bad-pull fraction |",
             "|---|---:|---:|---:|"]
    for name, row in report["arms"].items():
        round_text = "—" if row["mean_recovery_round_among_recovered"] is None else f"{row['mean_recovery_round_among_recovered']:.2f}"
        lines.append(f"| {name} | {row['recovery_rate']:.3f} ({row['recovered_n']}/{report['eligible_count']}) | {round_text} | {row['mean_bad_pull_fraction']:.3f} |")
    lines += ["", "## Preregistered paired contrasts", ""]
    for name, row in report["contrasts"].items():
        if "mean_recovery_uplift" in row:
            lines.append(f"- `{name}`: uplift {row['mean_recovery_uplift']:+.3f}; 97.5% paired bootstrap CI [{row['ci97_5'][0]:+.3f}, {row['ci97_5'][1]:+.3f}].")
        else:
            lines.append(f"- `{name}` (secondary): difference-in-differences {row['mean_difference_in_differences']:+.3f}; 95% CI [{row['ci95'][0]:+.3f}, {row['ci95'][1]:+.3f}].")
    lines += ["", "Both primary comparisons start from the same false-consensus posterior state per seed. The topology comparator changes only post-checkpoint sharing structure. See the JSON artifact for all paired outcomes, exact seeds, hashes and limitations.", ""]
    (ROOT / "research" / "results" / f"n5-10{suffix}-false-consensus-recovery.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    followup = "--followup" in sys.argv[1:]
    if followup:
        preregistration = ROOT / "research" / "prereg" / "n5-10-followup-false-consensus-recovery-v1.md"
        seeds = tuple(range(20_000, 25_000))
        minimum = 400
    else:
        preregistration, seeds, minimum = PREREG, SEEDS, 200
    result = run(seeds, preregistration=preregistration, minimum_eligible=minimum)
    write_result(result)
    print(json.dumps({"task_id": "N5-10", "eligible": result["eligible_count"],
                      "verdict": result["verdict"], "runtime_seconds": result["runtime_seconds"]}, indent=2))

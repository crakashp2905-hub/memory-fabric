"""N5-04 synthetic comparison of evidence aggregation policies.

The frozen protocol is research/prereg/n5-04-aggregation-policies-v1.md.
This benchmark is synthetic and intentionally separates source-root votes,
reporter reputation, and source evidence-quality metadata.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "research" / "results" / "n5-04-aggregation-policies.json"
MARKDOWN_PATH = ROOT / "research" / "results" / "n5-04-aggregation-policies.md"
TEST_PATH = ROOT / "research" / "results" / "n5-04-aggregation-tests.xml"
ROOT_MULTIPLICITIES = (1, 1, 2, 2, 4, 4, 8, 8)
QUALITY_RATES = {"high": 0.85, "medium": 0.65, "low": 0.55}
QUALITY_ORDER = ("high", "high", "medium", "medium", "medium", "low", "low", "low")
EVAL_SEEDS = (201, 202, 203, 204, 205)
WAVES = 8
TASKS_PER_EVAL_SEED = 500


@dataclass(frozen=True)
class Report:
    task_id: int
    root_id: int
    reporter: int
    quality: str
    value: int
    wave: int


@dataclass(frozen=True)
class Task:
    truth: int
    reports: tuple[Report, ...]


@dataclass(frozen=True)
class Dataset:
    seed: int
    tasks: tuple[Task, ...]
    reputation: tuple[float, ...]
    calibration_correct: tuple[int, ...]
    report_sha256: str

    def to_json(self) -> dict[str, object]:
        return {
            "seed": self.seed,
            "reputation": list(self.reputation),
            "calibration_correct": list(self.calibration_correct),
            "report_sha256": self.report_sha256,
            "tasks": [
                {
                    "task_id": index,
                    "truth": task.truth,
                    "reports": [report.__dict__ for report in task.reports],
                }
                for index, task in enumerate(self.tasks)
            ],
        }


def _logit(probability: float) -> float:
    return math.log(probability / (1.0 - probability))


def generate(seed: int, task_count: int) -> Dataset:
    """Generate balanced tasks plus an isolated 40-case reporter calibration set."""
    if task_count < 2 or task_count % 2:
        raise ValueError("task_count must be a positive even number")
    rng = random.Random(seed)
    truth_labels = [0, 1] * (task_count // 2)
    rng.shuffle(truth_labels)

    calibration_rng = random.Random(seed + 10_000)
    agent_accuracy = tuple(0.55 + 0.10 * (index % 4) for index in range(16))
    reputation: list[float] = []
    calibration_correct: list[int] = []
    for accuracy in agent_accuracy:
        correct = sum(calibration_rng.random() < accuracy for _ in range(40))
        calibration_correct.append(correct)
        reputation.append(min(0.95, max(0.5, (correct + 1) / 41)))

    tasks: list[Task] = []
    canonical_reports: list[dict[str, int | str]] = []
    for task_id, truth in enumerate(truth_labels):
        reports: list[Report] = []
        for root_id, (multiplicity, quality) in enumerate(
            zip(ROOT_MULTIPLICITIES, QUALITY_ORDER, strict=True)
        ):
            source_value = truth if rng.random() < QUALITY_RATES[quality] else 1 - truth
            for copy_index in range(multiplicity):
                reporter = (root_id * 7 + copy_index) % 16
                wave = 1 + (root_id + copy_index) % WAVES
                report = Report(task_id, root_id, reporter, quality, source_value, wave)
                reports.append(report)
                canonical_reports.append(
                    {
                        "task_id": task_id,
                        "root_id": root_id,
                        "reporter": reporter,
                        "quality": quality,
                        "value": source_value,
                        "wave": wave,
                        "truth": truth,
                    }
                )
        tasks.append(Task(truth, tuple(reports)))
    payload = json.dumps(canonical_reports, sort_keys=True, separators=(",", ":")).encode()
    return Dataset(
        seed,
        tuple(tasks),
        tuple(reputation),
        tuple(calibration_correct),
        hashlib.sha256(payload).hexdigest(),
    )


def predict(reports: tuple[Report, ...], policy: str, reputation: tuple[float, ...]) -> int | None:
    """Return 0, 1, or None (ABSTAIN) using one frozen aggregation policy."""
    if not reports:
        return None
    totals = [0.0, 0.0]
    if policy == "majority":
        for report in reports:
            totals[report.value] += 1.0
    elif policy == "reputation":
        for report in reports:
            totals[report.value] += _logit(reputation[report.reporter])
    elif policy in {"independent_root", "evidence_quality"}:
        by_root: dict[int, Report] = {}
        for report in reports:
            by_root.setdefault(report.root_id, report)
        for report in by_root.values():
            weight = (
                _logit(QUALITY_RATES[report.quality])
                if policy == "evidence_quality"
                else 1.0
            )
            totals[report.value] += weight
    else:
        raise ValueError(f"unknown aggregation policy: {policy}")
    if math.isclose(totals[0], totals[1], rel_tol=0.0, abs_tol=1e-12):
        return None
    return 0 if totals[0] > totals[1] else 1


POLICIES = ("majority", "reputation", "independent_root", "evidence_quality")
ARMS = POLICIES + ("oracle",)


def utility(action: int | None, truth: int) -> int:
    return 0 if action is None else (1 if action == truth else -1)


def pilot_is_degenerate(rows: dict[str, dict[str, int | float]]) -> bool:
    """Seed-200 stop rule: any policy perfectly matches oracle utility and errors."""
    return any(
        rows[policy]["mean_utility"] == 1.0 and rows[policy]["action_errors"] == 0
        for policy in POLICIES
        if policy in rows
    )


def score(dataset: Dataset) -> dict[str, object]:
    """Score all policies on identical tasks and report waves, with oracle checks."""
    per_policy: dict[str, list[dict[str, object]]] = {policy: [] for policy in ARMS}
    oracle_utility = 1.0
    for task_id, task in enumerate(dataset.tasks):
        actions: dict[str, list[int | None]] = {policy: [] for policy in ARMS}
        for wave in range(1, WAVES + 1):
            arrived = tuple(report for report in task.reports if report.wave <= wave)
            for policy in POLICIES:
                actions[policy].append(predict(arrived, policy, dataset.reputation))
            actions["oracle"].append(task.truth)
        correct_roots = sum(
            1 for root_id in range(8)
            if any(report.root_id == root_id and report.value == task.truth for report in task.reports)
        )
        minority = 1 <= correct_roots <= 3
        for policy, policy_actions in actions.items():
            action = policy_actions[-1]
            is_wrong = action is not None and action != task.truth
            stable_wave = next(
                (
                    wave
                    for index, wave in enumerate(range(1, WAVES + 1))
                    if all(later == policy_actions[index] for later in policy_actions[index:])
                ),
                None,
            )
            per_policy[policy].append(
                {
                    "task_id": task_id,
                    "truth": task.truth,
                    "action": action,
                    "utility": utility(action, task.truth),
                    "wrong_decisive": bool(is_wrong),
                    "decisive": action is not None,
                    "minority_truth": minority,
                    "minority_correct": bool(minority and action == task.truth),
                    "convergence_wave": stable_wave,
                    "converged": stable_wave is not None,
                }
            )
            if utility(action, task.truth) > oracle_utility:
                raise RuntimeError("policy utility exceeded unhandicapped oracle")

    summary: dict[str, dict[str, int | float]] = {}
    for policy, rows in per_policy.items():
        decisive = [row for row in rows if row["decisive"]]
        wrong = sum(bool(row["wrong_decisive"]) for row in rows)
        minority_rows = [row for row in rows if row["minority_truth"]]
        converged = [row["convergence_wave"] for row in rows if row["converged"]]
        summary[policy] = {
            "task_count": len(rows),
            "mean_utility": sum(int(row["utility"]) for row in rows) / len(rows),
            "accuracy_decisive": (
                1.0 - wrong / len(decisive) if decisive else 0.0
            ),
            "coverage": len(decisive) / len(rows),
            "action_errors": wrong,
            "wrong_decision_rate": wrong / len(decisive) if decisive else 0.0,
            "abstentions": len(rows) - len(decisive),
            "minority_task_count": len(minority_rows),
            "minority_recovery": (
                sum(bool(row["minority_correct"]) for row in minority_rows)
                / len(minority_rows)
                if minority_rows
                else 0.0
            ),
            "convergence_rate": len(converged) / len(rows),
            "mean_convergence_wave": sum(int(wave) for wave in converged) / len(converged)
            if converged
            else None,
        }
    return {"summary": summary, "tasks": per_policy}


def paired_bootstrap(score_rows: dict[str, list[dict[str, object]]], seed: int) -> dict[str, object]:
    """Paired task bootstrap for mean utility and evidence-quality contrast."""
    rng = random.Random(seed)
    count = len(score_rows["majority"])
    samples: dict[str, list[float]] = {policy: [] for policy in POLICIES}
    contrasts: list[float] = []
    headroom_shares: list[float] = []
    for _ in range(10_000):
        indices = [rng.randrange(count) for _ in range(count)]
        means = {
            policy: sum(
                int(score_rows[policy][index]["utility"]) for index in indices
            ) / count
            for policy in POLICIES
        }
        for policy in POLICIES:
            samples[policy].append(means[policy])
        baseline = max(means["majority"], means["reputation"])
        effect = means["evidence_quality"] - baseline
        contrasts.append(effect)
        headroom = 1.0 - baseline
        headroom_shares.append(effect / headroom if headroom > 0 else 0.0)

    def interval(values: list[float]) -> list[float]:
        ordered = sorted(values)
        return [ordered[249], ordered[9749]]

    return {
        "replicates": 10_000,
        "policy_mean_utility_95ci": {
            policy: interval(values) for policy, values in samples.items()
        },
        "evidence_quality_minus_best_baseline_95ci": interval(contrasts),
        "headroom_share_95ci": interval(headroom_shares),
        "bootstrap_seed": seed,
    }


def run() -> dict[str, object]:
    """Run the pilot screen, then (only if valid) the frozen held-out seeds."""
    import xml.etree.ElementTree as ET

    junit = ET.parse(TEST_PATH).getroot()
    cases = len(list(junit.iter("testcase")))
    failures = len(list(junit.iter("failure")))
    errors = len(list(junit.iter("error")))
    skipped = len(list(junit.iter("skipped")))
    if cases < 7 or failures or errors or skipped:
        raise RuntimeError("N5-04 focused tests must pass with no skips")

    pilot = generate(200, 100)
    pilot_result = score(pilot)
    pilot_summary = pilot_result["summary"]
    assert isinstance(pilot_summary, dict)
    if pilot_is_degenerate(pilot_summary):
        held_out: list[dict[str, object]] = []
        stopped = True
    else:
        held_out = []
        stopped = False
        for seed in EVAL_SEEDS:
            dataset = generate(seed, TASKS_PER_EVAL_SEED)
            result = score(dataset)
            held_out.append(
                {
                    "seed": seed,
                    "task_count": len(dataset.tasks),
                    "report_sha256": dataset.report_sha256,
                    "summary": result["summary"],
                    "paired_bootstrap": paired_bootstrap(
                        result["tasks"], seed=seed + 50_000
                    ),
                }
            )
    for seed_row in held_out:
        summaries = seed_row["summary"]
        assert isinstance(summaries, dict)
        oracle = 1.0
        if any(float(policy["mean_utility"]) > oracle for policy in summaries.values()):
            raise RuntimeError(f"oracle ceiling exceeded on seed {seed_row['seed']}")

    baseline_rows = [row["summary"] for row in held_out]
    contrast: list[float] = []
    for summaries in baseline_rows:
        assert isinstance(summaries, dict)
        baseline = max(
            float(summaries[policy]["mean_utility"])
            for policy in ("majority", "reputation")
        )
        headroom = 1.0 - baseline
        contrast.append(
            (float(summaries["evidence_quality"]["mean_utility"]) - baseline) / headroom
            if headroom > 0
            else 0.0
        )

    source = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()
    dirty = bool(
        subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )
    result: dict[str, object] = {
        "schema": "memory-fabric-n5-04-aggregation-policies/1",
        "task_id": "N5-04",
        "acceptance_passed": True,
        "evidence_level": "SIMULATED",
        "source": {
            "commit": source,
            "dirty_before_result_write": dirty,
            "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        },
        "protocol": "research/prereg/n5-04-aggregation-policies-v1.md",
        "pilot": {
            "seed": 200,
            "report_sha256": pilot.report_sha256,
            "summary": pilot_summary,
            "paired_bootstrap": paired_bootstrap(pilot_result["tasks"], seed=50_200),
            "stopped_for_metric_degeneracy": stopped,
        },
        "held_out": held_out,
        "pooled_task_counts": {
            "pilot_tasks": len(pilot.tasks),
            "held_out_tasks": sum(int(row["task_count"]) for row in held_out),
            "held_out_minority_tasks": sum(
                int(row["summary"]["majority"]["minority_task_count"])
                for row in held_out
            ),
            "held_out_seed_count": len(held_out),
        },
        "manifest": {
            "path": "research/results/n5-04-aggregation-manifest.json",
            "seeds": [200] + list(EVAL_SEEDS) if not stopped else [200],
            "sha256": None,
        },
        "confirmatory_contrast": {
            "candidate": "evidence_quality",
            "baseline": "best of majority and reputation",
            "per_seed_headroom_share": contrast,
            "mean_headroom_share": sum(contrast) / len(contrast) if contrast else None,
            "registered_target": 0.25,
            "target_met": bool(contrast) and sum(contrast) / len(contrast) >= 0.25,
            "interpretable": bool(held_out) and all(
                float(max(row["summary"][p]["mean_utility"] for p in ("majority", "reputation"))) < 1.0
                for row in held_out
            ),
        },
        "configuration": {
            "held_out_seeds": list(EVAL_SEEDS),
            "tasks_per_seed": TASKS_PER_EVAL_SEED,
            "root_multiplicities": list(ROOT_MULTIPLICITIES),
            "quality_rates": QUALITY_RATES,
            "waves": WAVES,
            "synthetic_only": True,
        },
        "tests": {
            "junit": TEST_PATH.relative_to(ROOT).as_posix(),
            "reported_test_cases": cases,
            "failures": failures,
            "errors": errors,
            "skipped": skipped,
        },
        "limitations": [
            "Evidence-quality tiers are synthetic assumptions and do not estimate real source reliability.",
            "Source-root deduplication is only as reliable as the benchmark's supplied provenance labels.",
            "Reporter reputation is simulated from a separate calibration split and is not an operational trust score.",
        ],
    }
    datasets = [pilot]
    if not stopped:
        datasets.extend(generate(seed, TASKS_PER_EVAL_SEED) for seed in EVAL_SEEDS)
    manifest = {
        "schema": "memory-fabric-n5-04-aggregation-manifest/1",
        "protocol": "research/prereg/n5-04-aggregation-policies-v1.md",
        "seeds": [dataset.to_json() for dataset in datasets],
    }
    manifest_bytes = (json.dumps(manifest, indent=2) + "\n").encode()
    manifest_path = ROOT / "research" / "results" / "n5-04-aggregation-manifest.json"
    manifest_path.write_bytes(manifest_bytes)
    result["manifest"]["sha256"] = hashlib.sha256(manifest_bytes).hexdigest()
    REPORT_PATH.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    if held_out:
        rows = []
        for policy in (*POLICIES, "oracle"):
            seed_summaries = [row["summary"][policy] for row in held_out]
            mean_utility = sum(float(row["mean_utility"]) for row in seed_summaries) / len(seed_summaries)
            mean_accuracy = sum(float(row["accuracy_decisive"]) for row in seed_summaries) / len(seed_summaries)
            total_errors = sum(int(row["action_errors"]) for row in seed_summaries)
            mean_minority = sum(float(row["minority_recovery"]) for row in seed_summaries) / len(seed_summaries)
            mean_convergence = sum(float(row["mean_convergence_wave"]) for row in seed_summaries) / len(seed_summaries)
            rows.append(
                f"| {policy} | {mean_utility:.3f} | {mean_accuracy:.3f} | "
                f"{total_errors} | {mean_minority:.3f} | {mean_convergence:.2f} |"
            )
        confidence_rows = [
            f"| {row['seed']} | {row['paired_bootstrap']['evidence_quality_minus_best_baseline_95ci'][0]:.3f} "
            f"to {row['paired_bootstrap']['evidence_quality_minus_best_baseline_95ci'][1]:.3f} | "
            f"{row['paired_bootstrap']['headroom_share_95ci'][0]:.3f} to "
            f"{row['paired_bootstrap']['headroom_share_95ci'][1]:.3f} |"
            for row in held_out
        ]
        conclusion = (
            f"Evidence-quality mean headroom share: **{result['confirmatory_contrast']['mean_headroom_share']:.3f}** "
            f"(registered target 0.250; target met: **{result['confirmatory_contrast']['target_met']}**)."
        )
    else:
        rows = []
        confidence_rows = []
        conclusion = "The seed-200 pilot saturated the registered baseline metric; held-out evaluation was stopped."
    markdown = (
        "# N5-04 aggregation policy benchmark\n\n"
        "Protocol: `research/prereg/n5-04-aggregation-policies-v1.md`. The pilot used "
        f"100 tasks; held-out evaluation used {sum(int(row['task_count']) for row in held_out)} "
        f"tasks across seeds {', '.join(str(seed) for seed in EVAL_SEEDS) if held_out else 'none'}. "
        f"Pilot degeneracy stop: **{stopped}**.\n\n"
        f"{conclusion}\n\n"
        "## Held-out seed means\n\n"
        "| policy | utility | decisive accuracy | action errors / 2,500 | minority recovery | mean convergence wave |\n"
        "|---|---:|---:|---:|---:|---:|\n"
        + "\n".join(rows)
        + "\n\n## Paired bootstrap intervals\n\n"
        "Intervals resample tasks within each seed (10,000 replicates). The first interval is "
        "evidence-quality utility minus the best of majority/reputation; the second is its "
        "per-seed share of oracle headroom.\n\n"
        "| seed | utility contrast 95% CI | headroom share 95% CI |\n|---:|---:|---:|\n"
        + "\n".join(confidence_rows)
        + "\n\nThe explicit oracle is perfect by construction, as required. The full 15.8 MB input "
        "manifest is `research/results/n5-04-aggregation-manifest.json`; the JSON result binds "
        "its SHA-256 and all per-seed counts, errors, minority recovery, convergence, and test status. "
        "The generator's quality rates are synthetic assumptions, not real-world source reliability "
        "estimates. This result does not establish field efficacy or action safety.\n"
    )
    MARKDOWN_PATH.write_text(markdown, encoding="utf-8")
    return result


def main() -> int:
    result = run()
    print(json.dumps({
        "pilot": result["pilot"]["summary"],
        "target_met": result["confirmatory_contrast"]["target_met"],
        "mean_headroom_share": result["confirmatory_contrast"]["mean_headroom_share"],
        "held_out_seeds": len(result["held_out"]),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

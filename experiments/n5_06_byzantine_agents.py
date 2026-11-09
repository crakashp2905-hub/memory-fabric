"""N5-06 controlled Byzantine-agent simulation.

Synthetic evidence only. See the frozen threat model in
research/prereg/n5-06-byzantine-agents-v1.md.
"""
from __future__ import annotations

import hashlib
import json
import random
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean

from experiments.n5_04_aggregation import (
    ARMS,
    POLICIES,
    QUALITY_ORDER,
    QUALITY_RATES,
    ROOT_MULTIPLICITIES,
    _logit,
)

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = "research/prereg/n5-06-byzantine-agents-v1.md"
REPORT_PATH = ROOT / "research" / "results" / "n5-06-byzantine-agents.json"
MARKDOWN_PATH = ROOT / "research" / "results" / "n5-06-byzantine-agents.md"
TEST_PATH = ROOT / "research" / "results" / "n5-06-byzantine-tests.xml"
BEHAVIORS = ("lie", "replay", "copy", "selective_withdrawal")
FAULT_FRACTIONS = (0.0, 0.10, 0.25, 0.40)
EVAL_SEEDS = (301, 302, 303, 304, 305)
TASKS_PER_SEED = 200
PILOT_SEED = 300
PILOT_TASKS = 100
REPLAY_LIMIT = 3


@dataclass(frozen=True)
class ByzantineReport:
    task_id: int
    root_id: int
    reporter: int
    quality: str
    value: int
    wave: int
    byzantine: bool
    attack: str
    replay_index: int


@dataclass(frozen=True)
class Dataset:
    seed: int
    behavior: str
    fault_fraction: float
    faulty_reporters: tuple[int, ...]
    reporter_reputation: tuple[float, ...]
    truths: tuple[int, ...]
    reports: tuple[ByzantineReport, ...]
    report_sha256: str


def _stream_seed(seed: int, behavior: str, fraction: float, task: int) -> int:
    value = f"n5-06-v1:{seed}:{behavior}:{fraction:.2f}:{task}".encode()
    return int.from_bytes(hashlib.sha256(value).digest()[:8], "big")


def _shared_truths(seed: int, task_count: int) -> tuple[int, ...]:
    truths = [0, 1] * (task_count // 2)
    random.Random(_stream_seed(seed, "shared-truth", 0.0, -2)).shuffle(truths)
    return tuple(truths)


def generate(seed: int, task_count: int, behavior: str, fault_fraction: float) -> Dataset:
    """Generate one task set under an explicit identity-level Byzantine fraction."""
    if task_count < 2 or task_count % 2:
        raise ValueError("task_count must be a positive even number")
    if behavior not in BEHAVIORS:
        raise ValueError(f"unsupported behavior: {behavior}")
    if not 0 <= fault_fraction <= 0.5:
        raise ValueError("fault_fraction must be between 0 and 0.5")
    reporter_count = 16
    faulty_count = int(reporter_count * fault_fraction)
    identity_rng = random.Random(_stream_seed(seed, "byzantine-identities", 0.0, -1))
    identity_order = identity_rng.sample(range(reporter_count), reporter_count)
    faulty = tuple(sorted(identity_order[:faulty_count]))
    calibration_rng = random.Random(_stream_seed(seed, "shared-calibration", 0.0, -3))
    accuracies = tuple(0.55 + 0.10 * (index % 4) for index in range(reporter_count))
    reputation = tuple(
        min(0.95, max(0.5, (sum(calibration_rng.random() < accuracy for _ in range(40)) + 1) / 41))
        for accuracy in accuracies
    )
    truths = _shared_truths(seed, task_count)
    reports: list[ByzantineReport] = []
    canonical: list[dict[str, object]] = []

    for task_id, truth in enumerate(truths):
        # Use the same honest world for every attack intervention. The attack
        # changes only faulty reporters' behavior/availability.
        rng = random.Random(_stream_seed(seed, "shared-world", 0.0, task_id))
        root_values: dict[int, int] = {}
        slots: list[tuple[int, int, str, int, int]] = []
        for root_id, (multiplicity, quality) in enumerate(
            zip(ROOT_MULTIPLICITIES, QUALITY_ORDER, strict=True)
        ):
            root_value = truth if rng.random() < QUALITY_RATES[quality] else 1 - truth
            root_values[root_id] = root_value
            for copy_index in range(multiplicity):
                reporter = (root_id * 7 + copy_index) % reporter_count
                wave = 1 + (root_id + copy_index) % 8
                slots.append((root_id, reporter, quality, wave, copy_index))

        honest_values = [root_values[root_id] for root_id, *_ in slots]
        observed_mode = 0 if sum(value == 0 for value in honest_values) >= sum(
            value == 1 for value in honest_values
        ) else 1
        for root_id, reporter, quality, wave, copy_index in slots:
            is_bad = reporter in faulty
            base = root_values[root_id]
            attack_value = base
            attack = "honest"
            copies = 1
            if is_bad:
                attack = behavior
                if behavior == "lie":
                    attack_value = 1 - truth
                elif behavior == "copy":
                    attack_value = observed_mode
                elif behavior == "selective_withdrawal":
                    if base == truth:
                        continue
                    attack_value = base
                elif behavior == "replay":
                    attack_value = base
                    copies = REPLAY_LIMIT
            for replay_index in range(copies):
                row = ByzantineReport(
                    task_id, root_id, reporter, quality, attack_value, wave,
                    is_bad, attack, replay_index,
                )
                reports.append(row)
                canonical.append(asdict(row) | {"truth": truth})

    payload = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
    return Dataset(
        seed, behavior, fault_fraction, faulty, reputation, truths, tuple(reports),
        hashlib.sha256(payload).hexdigest(),
    )


def _predict(
    reports: tuple[ByzantineReport, ...], policy: str,
    reputation: tuple[float, ...],
) -> int | None:
    if not reports:
        return None
    totals = [0.0, 0.0]
    if policy == "majority":
        for report in reports:
            totals[report.value] += 1.0
    elif policy == "reputation":
        for report in reports:
            # Evaluation labels do not update reputation; the seed-fixed
            # calibration stream is shared by all counterfactual conditions.
            totals[report.value] += _logit(reputation[report.reporter])
    elif policy in {"independent_root", "evidence_quality"}:
        by_root: dict[int, ByzantineReport] = {}
        for report in reports:
            by_root.setdefault(report.root_id, report)
        for report in by_root.values():
            weight = _logit(QUALITY_RATES[report.quality]) if policy == "evidence_quality" else 1.0
            totals[report.value] += weight
    else:
        raise ValueError(f"unknown policy: {policy}")
    if abs(totals[0] - totals[1]) <= 1e-12:
        return None
    return 0 if totals[0] > totals[1] else 1


def _group_reports(dataset: Dataset) -> list[tuple[ByzantineReport, ...]]:
    grouped: list[list[ByzantineReport]] = [[] for _ in dataset.truths]
    for report in dataset.reports:
        grouped[report.task_id].append(report)
    return [tuple(rows) for rows in grouped]


def _score_policy(dataset: Dataset, policy: str) -> dict[str, object]:
    wrong = decisive = correct = abstentions = 0
    for truth, reports in zip(dataset.truths, _group_reports(dataset), strict=True):
        action = _predict(reports, policy, dataset.reporter_reputation)
        if action is None:
            abstentions += 1
        else:
            decisive += 1
            if action == truth:
                correct += 1
            else:
                wrong += 1
    count = len(dataset.truths)
    return {
        "task_count": count,
        "wrong_actions": wrong,
        "wrong_action_rate_all_tasks": wrong / count,
        "wrong_decision_rate": wrong / decisive if decisive else 0.0,
        "coverage": decisive / count,
        "abstention_rate": abstentions / count,
        "mean_utility": (correct - wrong) / count,
    }


def _percentile_interval(values: list[float]) -> list[float]:
    ordered = sorted(values)
    if len(ordered) < 2:
        raise ValueError("at least two bootstrap replicates are required")
    return [ordered[int((len(ordered) - 1) * 0.025)], ordered[int((len(ordered) - 1) * 0.975)]]


def paired_bootstrap(
    datasets: list[Dataset], policy: str, behavior: str, fault_fraction: float,
    *, replicates: int = 10_000, seed: int = 1,
) -> dict[str, object]:
    """Equal-seed paired bootstrap against the same attack's zero-fault arm."""
    attacked = [dataset for dataset in datasets if dataset.behavior == behavior and dataset.fault_fraction == fault_fraction]
    baseline = [dataset for dataset in datasets if dataset.behavior == behavior and dataset.fault_fraction == 0.0]
    if len(attacked) != len(EVAL_SEEDS) or len(baseline) != len(EVAL_SEEDS):
        raise ValueError("bootstrap requires all five attacked and baseline seeds")
    per_seed: list[tuple[list[int], list[int]]] = []
    for arm in attacked:
        base = next(row for row in baseline if row.seed == arm.seed)
        if arm.truths != base.truths:
            raise ValueError("paired arms must share task truths")
        arm_wrong: list[int] = []
        base_wrong: list[int] = []
        arm_groups = _group_reports(arm)
        base_groups = _group_reports(base)
        for truth, arm_rows, base_rows in zip(arm.truths, arm_groups, base_groups, strict=True):
            arm_action = _predict(arm_rows, policy, arm.reporter_reputation)
            base_action = _predict(base_rows, policy, base.reporter_reputation)
            arm_wrong.append(int(arm_action is not None and arm_action != truth))
            base_wrong.append(int(base_action is not None and base_action != truth))
        per_seed.append((arm_wrong, base_wrong))
    observed = mean(
        mean(a - b for a, b in zip(arm_wrong, base_wrong, strict=True))
        for arm_wrong, base_wrong in per_seed
    )
    rng = random.Random(seed)
    deltas: list[float] = []
    if replicates < 500:
        raise ValueError("replicates must be at least 500 for percentile interval stability")
    for _ in range(replicates):
        seed_deltas = []
        for arm_wrong, base_wrong in per_seed:
            n = len(arm_wrong)
            indices = [rng.randrange(n) for _ in range(n)]
            seed_deltas.append(
                sum(arm_wrong[index] - base_wrong[index] for index in indices) / n
            )
        deltas.append(mean(seed_deltas))
    return {
        "replicates": replicates,
        "seed": seed,
        "mean_paired_change_wrong_action_rate": observed,
        "paired_change_95ci": _percentile_interval(deltas),
    }


def _run_conditions(
    seeds: tuple[int, ...], task_count: int, *, bootstrap: bool,
    bootstrap_replicates: int = 10_000,
) -> list[dict[str, object]]:
    rows = []
    for behavior in BEHAVIORS:
        behavior_datasets: dict[float, list[Dataset]] = {}
        for fraction in FAULT_FRACTIONS:
            per_seed = []
            datasets = []
            for seed in seeds:
                dataset = generate(seed, task_count, behavior, fraction)
                datasets.append(dataset)
                per_seed.append({
                    "seed": seed,
                    "faulty_reporters": list(dataset.faulty_reporters),
                    "faulty_reporter_count": len(dataset.faulty_reporters),
                    "task_count": task_count,
                    "report_sha256": dataset.report_sha256,
                    "summary": {policy: _score_policy(dataset, policy) for policy in POLICIES},
                })
            behavior_datasets[fraction] = datasets
            pooled = {
                policy: {
                    key: mean(float(seed_row["summary"][policy][key]) for seed_row in per_seed)
                    for key in (
                        "wrong_actions", "wrong_action_rate_all_tasks", "wrong_decision_rate",
                        "coverage", "abstention_rate", "mean_utility",
                    )
                }
                for policy in POLICIES
            }
            intervals = {
                policy: paired_bootstrap(
                    [*datasets, *behavior_datasets[0.0]], policy, behavior, fraction,
                    replicates=bootstrap_replicates,
                    seed=90_000 + int(fraction * 100) * 10 + BEHAVIORS.index(behavior) * 100 + POLICIES.index(policy),
                )
                for policy in POLICIES
            } if fraction and bootstrap else {policy: {"replicates": 0, "seed": None,
                                          "mean_paired_change_wrong_action_rate": 0.0,
                                          "paired_change_95ci": [0.0, 0.0]}
                                for policy in POLICIES}
            rows.append({
                "behavior": behavior,
                "fault_fraction_requested": fraction,
                "faulty_identity_count": int(16 * fraction),
                "fault_fraction_realized": int(16 * fraction) / 16,
                "per_seed": per_seed,
                "pooled_equal_seed_mean": pooled,
                "paired_vs_zero_fault": intervals,
            })
    return rows


def run() -> dict[str, object]:
    import xml.etree.ElementTree as ET

    root = ET.parse(TEST_PATH).getroot()
    test_cases = len(list(root.iter("testcase")))
    failures = len(list(root.iter("failure")))
    errors = len(list(root.iter("error")))
    skipped = len(list(root.iter("skipped")))
    if test_cases < 7 or failures or errors or skipped:
        raise RuntimeError("N5-06 tests must pass with no skips")
    pilot = _run_conditions((PILOT_SEED,), PILOT_TASKS, bootstrap=False)
    held_out = _run_conditions(EVAL_SEEDS, TASKS_PER_SEED, bootstrap=True)
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()
    dirty = bool(subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip())
    result: dict[str, object] = {
        "schema": "memory-fabric-n5-06-byzantine-agents/1",
        "task_id": "N5-06",
        "acceptance_passed": True,
        "evidence_level": "SIMULATED",
        "source": {"commit": commit, "dirty_before_result_write": dirty,
                   "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
        "protocol": PROTOCOL,
        "protocol_sha256": hashlib.sha256((ROOT / PROTOCOL).read_bytes()).hexdigest(),
        "threat_model": {
            "faulty_identity_fractions_requested": list(FAULT_FRACTIONS),
            "faulty_identity_fractions_realized": [int(16 * rate) / 16 for rate in FAULT_FRACTIONS],
            "attack_behaviors": list(BEHAVIORS),
            "attacker_knowledge": "knows truth and all honest report values within each task",
            "identity_model": "fixed reporter identities within each task; no churn",
            "root_authenticity": "root labels assumed accurate; root compromise is excluded",
        },
        "configuration": {"pilot_seed": PILOT_SEED, "pilot_tasks": PILOT_TASKS,
                          "evaluation_seeds": list(EVAL_SEEDS), "tasks_per_seed": TASKS_PER_SEED,
                          "conditions": len(BEHAVIORS) * len(FAULT_FRACTIONS),
                          "policies": list(POLICIES), "arms": list(ARMS),
                          "replay_limit": REPLAY_LIMIT},
        "pilot": pilot,
        "held_out": held_out,
        "skipped_conditions": [],
        "tests": {"junit": TEST_PATH.relative_to(ROOT).as_posix(),
                  "reported_test_cases": test_cases, "failures": failures,
                  "errors": errors, "skipped": skipped},
        "limitations": [
            "Synthetic binary tasks and source reliability rates do not estimate field behavior.",
            "Attackers are given ground truth and are stronger than typical uninformed agents.",
            "Faults are reporter identities; forged or compromised provenance roots are excluded.",
            "The experiment evaluates aggregation only and provides no authorization guarantee.",
        ],
    }
    REPORT_PATH.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    markdown = [
        "# N5-06 Byzantine-agent simulation", "",
        f"Protocol: `{PROTOCOL}`. Synthetic conditional evidence only. Faulty reporters know task truth; realized identity fractions are 0%, 0%, 18.75%, and 37.5% for the requested 0%, 10%, 25%, and 40% levels.", "",
        "## Held-out results", "",
        "Equal-weight means across five seeds; each cell is wrong actions / all tasks (coverage). Paired bootstrap intervals compare against the same behavior's zero-fault condition.", "",
        "| behavior | requested faults | policy | wrong action rate | coverage | paired change (95% CI) |", "|---|---:|---|---:|---:|---:|",
    ]
    for row in held_out:
        for policy in POLICIES:
            stats = row["pooled_equal_seed_mean"][policy]
            delta = row["paired_vs_zero_fault"][policy]["paired_change_95ci"]
            markdown.append(
                f"| {row['behavior']} | {row['fault_fraction_requested']:.0%} | {policy} | "
                f"{stats['wrong_action_rate_all_tasks']:.3f} | {stats['coverage']:.3f} | "
                f"{delta[0]:+.3f} to {delta[1]:+.3f} |"
            )
    markdown += ["", "## Interpretation limits", "",
                 "See the preregistration for the full threat model. These results do not establish live Byzantine resilience, root authenticity, or action safety.", ""]
    MARKDOWN_PATH.write_text("\n".join(markdown), encoding="utf-8")
    return result


def main() -> int:
    result = run()
    print(json.dumps({"task_id": result["task_id"], "conditions": result["configuration"]["conditions"],
                      "held_out_seed_count": len(EVAL_SEEDS), "evidence_level": result["evidence_level"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

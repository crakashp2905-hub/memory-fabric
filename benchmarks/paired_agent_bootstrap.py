"""Pair task-level outcomes from the registered matched-agent benchmark."""
from __future__ import annotations

import hashlib
import json
import platform
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from benchmarks.stats import paired_bootstrap  # noqa: E402

SOURCE = ROOT / "research/results/r3-02-matched-agent-arms.json"
SEEDS = (701, 709, 719)
AGENT_COUNT = 50
ARMS = ("isolated", "pooled_shared", "blanket_retraction", "memory_fabric")
BOOTSTRAP_SEED = 40201
RESAMPLES = 20_000


def _task_success(row: dict[str, Any], task: dict[str, Any]) -> float:
    counts = task["decision_counts"]
    correct = counts["allowed"] if task["expected"] == "allow" else counts["abstained"]
    return correct / row["agent_count"]


def build_report(source: dict[str, Any]) -> dict[str, Any]:
    rows = [row for row in source["rows"] if row["agent_count"] == AGENT_COUNT
            and row["seed"] in SEEDS and row["arm"] in ARMS]
    by_arm = {arm: {task["task_id"]: _task_success(row, task)
                    for row in rows if row["arm"] == arm
                    for task in row["task_manifest"]}
              for arm in ARMS}
    task_ids = sorted(by_arm["memory_fabric"])
    if len(task_ids) != 24 or any(set(by_arm[arm]) != set(task_ids) for arm in ARMS):
        raise ValueError("matched 50-agent arms must have the same 24 registered task cases")

    comparisons = {}
    for arm in ARMS:
        if arm == "memory_fabric":
            continue
        interval = paired_bootstrap(
            [by_arm[arm][task_id] for task_id in task_ids],
            [by_arm["memory_fabric"][task_id] for task_id in task_ids],
            seed=BOOTSTRAP_SEED, resamples=RESAMPLES, clusters=task_ids)
        comparisons[arm] = {
            **interval,
            "sample_size_unique_task_cases": len(task_ids),
            "attempts_per_arm": len(task_ids) * AGENT_COUNT,
            "cluster_count": len(set(task_ids)),
        }

    prereg = ROOT / "research/prereg/matched-agent-arms-v1.md"
    return {
        "schema": "mf-paired-agent-bootstrap/1",
        "decision": "DESCRIPTIVE",
        "population": "synthetic_scripted",
        "source_result": "research/results/r3-02-matched-agent-arms.json",
        "source_result_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "source_commit": source.get("repo_commit"),
        "source_preregistration": "research/prereg/matched-agent-arms-v1.md",
        "preregistration_sha256": hashlib.sha256(prereg.read_bytes()).hexdigest(),
        "split_identity": {"name": "registered matched-agent v1 seeds",
                            "seeds": list(SEEDS), "agent_count": AGENT_COUNT,
                            "task_cases": task_ids},
        "method": {"estimand": "mean per-task success-rate difference (Memory Fabric minus baseline)",
                   "interval": "paired percentile bootstrap, 95%",
                   "resamples": RESAMPLES, "seed": BOOTSTRAP_SEED,
                   "correlation_assumption": "Agents within a task are not treated as independent; the 24 matched task cases are resampled as clusters. Inference assumes task clusters are exchangeable within this synthetic registered split."},
        "comparisons": comparisons,
        "input_sha256": {
            "benchmarks/paired_agent_bootstrap.py": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "benchmarks/stats.py": hashlib.sha256((ROOT / "benchmarks/stats.py").read_bytes()).hexdigest(),
            "tests/test_paired_agent_bootstrap.py": hashlib.sha256((ROOT / "tests/test_paired_agent_bootstrap.py").read_bytes()).hexdigest(),
        },
        "environment": {"python": platform.python_version(), "platform": platform.platform()},
        "limitations": ["This is a reanalysis of deterministic synthetic scripted agents, not model-agent evidence.",
                        "Only the registered 50-agent condition and seeds 701/709/719 are analyzed.",
                        "Intervals quantify task-cluster variability within this fixture, not external population uncertainty."],
    }


def main() -> int:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    report = build_report(source)
    out = ROOT / "research/results/r4-02-paired-agent-bootstrap.json"
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"comparisons": len(report["comparisons"]),
                      "task_cases": len(report["split_identity"]["task_cases"]),
                      "out": str(out)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

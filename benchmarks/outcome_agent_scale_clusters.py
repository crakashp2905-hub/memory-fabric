"""Exploratory 3/5/10/25/50-agent runs reported by unique task and seed cluster (W10-10).

    python -m benchmarks.outcome_agent_scale_clusters

Reuses the registered agent-scale workload (``benchmarks.agent_scale``) with the
same seeds, task ids and family mix at every agent count, and adds 3 agents. It
is labelled EXPLORATORY: the registered run's counts are unchanged.

More agents means more attempts on the same tasks, not more evidence. The
report therefore leads with unique tasks and seed clusters (the independent
units), gives accuracy per cluster with its spread, and states attempts per
unique task, so a 50-agent row cannot read as 50 times the sample.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Sequence

from .agent_scale import SEEDS, run

COUNTS = (3, 5, 10, 25, 50)
SCHEMA_ID = "memory-fabric.agent-scale-clusters.v1"


def summarize(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for count in sorted({row["agent_count"] for row in rows}):
        mine = [row for row in rows if row["agent_count"] == count]
        unique = {task["task_id"] for row in mine for task in row["task_manifest"]}
        attempts = sum(row["counts"]["attempted"] for row in mine)
        per_cluster = [row["counts"]["accuracy"] for row in mine if row["counts"]["accuracy"] is not None]
        out[str(count)] = {
            "clusters": len({row["seed"] for row in mine}),
            "unique_tasks": len(unique),
            "attempts": attempts,
            "attempts_per_unique_task": round(attempts / len(unique), 3) if unique else None,
            "accuracy_by_cluster": [round(value, 4) for value in per_cluster],
            "accuracy_min": round(min(per_cluster), 4) if per_cluster else None,
            "accuracy_max": round(max(per_cluster), 4) if per_cluster else None,
            "unsafe_actions": sum(row["counts"]["unsafe_actions"] for row in mine),
        }
    return out


def build() -> dict[str, Any]:
    rows = [run(seed, count, counts=COUNTS) for seed in SEEDS for count in COUNTS]
    for row in rows:
        row.pop("elapsed_s", None)  # host timing is not part of this summary
    return {"schema_id": SCHEMA_ID, "status": "EXPLORATORY", "seeds": list(SEEDS),
            "agent_counts": list(COUNTS), "sampling_unit": "seed cluster",
            "summary": summarize(rows),
            "note": "agent count multiplies attempts on the same tasks; it adds no independent units"}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    report = build()
    text = json.dumps(report, indent=1, sort_keys=True) + "\n"
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(text)
    for count, row in report["summary"].items():
        print(f"{count:>3} agents: {row['clusters']} clusters, {row['unique_tasks']} unique tasks, "
              f"{row['attempts']} attempts ({row['attempts_per_unique_task']} per task), "
              f"accuracy {row['accuracy_min']}..{row['accuracy_max']}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

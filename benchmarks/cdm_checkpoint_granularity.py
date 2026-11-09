"""Measure storage/integrity costs for local replay checkpoint schedules."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import time
from pathlib import Path
from typing import Any

from memory_fabric.causal_replay.bayes import BinaryNode
from memory_fabric.causal_replay.executor import create_execution_checkpoint, execute
from memory_fabric.causal_replay.policy import ThresholdPolicy
from memory_fabric.causal_replay.replay import deterministic_simulator
from memory_fabric.causal_replay.state import Observation
from memory_fabric.causal_replay.types import canonical_json


def run(seed: int = 20261109, event_count: int = 100) -> dict[str, Any]:
    if type(seed) is not int or type(event_count) is not int or not 10 <= event_count <= 500:
        raise ValueError("seed must be an integer and event_count must be 10..500")
    nodes = (BinaryNode("fault", (), {(): 0.2}),
             BinaryNode("alarm", ("fault",), {(False,): 0.1, (True,): 0.9}))
    simulator = deterministic_simulator(nodes)
    policy = ThresholdPolicy("fault")
    observations = tuple(Observation(f"granularity-{seed}-{i}", "alarm", bool(i % 2),
                                     f"sensor-{i % 4}", i) for i in range(event_count))
    schedules = {f"every_{interval}": tuple(sorted({event_count, *range(
        interval, event_count + 1, interval)}))
                 for interval in (1, 5, 10, 25, 50, 100)}
    schedules["terminal_only"] = (event_count,)
    prefix_executions = {end: execute(observations[:end], simulator=simulator,
        policy=policy, max_events=event_count) for end in sorted(
            {point for points in schedules.values() for point in points})}
    if any(not execution.complete or execution.status.value != "EXACT"
           for execution in prefix_executions.values()):
        raise RuntimeError("checkpoint benchmark requires complete exact local replay")

    rows = []
    for name, points in schedules.items():
        total_bytes = 0
        construction_ns = 0
        checkpoint_rows = []
        for end in points:
            started = time.perf_counter_ns()
            checkpoint = create_execution_checkpoint(prefix_executions[end],
                simulator=simulator, policy=policy)
            payload = canonical_json(checkpoint.payload()).encode("utf-8")
            elapsed = time.perf_counter_ns() - started
            total_bytes += len(payload)
            construction_ns += elapsed
            checkpoint_rows.append({"event_index": end, "prefix_events": end,
                "payload_bytes": len(payload), "checkpoint_sha256": checkpoint.checkpoint_digest,
                "construction_ns": elapsed})
        gaps = [right - left for left, right in zip((0, *points[:-1]), points)]
        rows.append({"schedule": name, "checkpoint_count": len(points),
            "total_payload_bytes": total_bytes,
            "mean_payload_bytes": total_bytes / len(points),
            "max_interval_events": max(gaps),
            "mean_interval_events": sum(gaps) / len(gaps),
            "construction_ns": construction_ns,
            # Current execute_from_checkpoint verifies by replaying the full stored prefix.
            "current_restore_prefix_replay_events": sum(points),
            "checkpoints": checkpoint_rows})
    return {"schema": "cdm-checkpoint-granularity-v1", "seed": seed,
        "event_count": event_count, "mode": "synthetic_exact_prefix_checkpoint_storage_and_integrity_work",
        "restore_speedup_claimed": False,
        "current_restore_behavior": "execute_from_checkpoint replays each checkpoint prefix; no restore speedup is implemented",
        "dependencies": "Python standard library only", "model_calls": 0, "network_calls": 0,
        "python": platform.python_version(), "platform": platform.platform(), "rows": rows,
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=20261109)
    parser.add_argument("--events", type=int, default=100)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    report = run(args.seed, args.events)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Generate competing-evidence chain, star, and fork dependency fixtures."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from memory_fabric.causal_replay.scheduler import dependency_frontier
from memory_fabric.causal_replay.state import Observation


def _graph(shape: str, size: int) -> dict[str, tuple[str, ...]]:
    ids = tuple(f"{shape}-{index}" for index in range(size))
    if shape == "chain":
        return {event_id: ((ids[index - 1],) if index else ())
                for index, event_id in enumerate(ids)}
    if shape == "star":
        return {event_id: ((ids[0],) if index else ())
                for index, event_id in enumerate(ids)}
    if shape == "fork":
        if size < 7:
            raise ValueError("fork requires at least seven events")
        parents: dict[str, tuple[str, ...]] = {event_id: () for event_id in ids}
        parents[ids[1]] = (ids[0],)
        parents[ids[2]] = (ids[1],)
        parents[ids[3]] = (ids[1],)
        parents[ids[4]] = (ids[0],)
        parents[ids[5]] = (ids[4],)
        parents[ids[6]] = (ids[4],)
        return parents
    raise ValueError("shape must be chain, star, or fork")


def run(size: int = 8) -> dict[str, Any]:
    if type(size) is not int or not 7 <= size <= 100:
        raise ValueError("size must be between 7 and 100")
    rows = []
    for shape in ("chain", "star", "fork"):
        dependencies = _graph(shape, size)
        event_ids = tuple(dependencies)
        observations = tuple(Observation(event_id, "fault", bool(index % 2),
            f"source-{index % 3}", index) for index, event_id in enumerate(event_ids))
        values = {item.value for item in observations}
        target_id = event_ids[1]
        frontier = dependency_frontier(event_ids, target_id,
            dependencies=dependencies, dependencies_complete=True)
        rows.append({"shape": shape, "event_count": size,
            "edge_count": sum(len(parents) for parents in dependencies.values()),
            "target_id": target_id, "frontier_ids": list(frontier),
            "frontier_size": len(frontier), "independent_event_count": size - len(frontier),
            "competing_evidence": len(values) > 1,
            "competing_values": sorted(values),
            "observations": [item.__dict__ for item in observations],
            "dependencies": {key: list(value) for key, value in dependencies.items()}})
    return {"schema": "cdm-dependency-shapes-v1", "mode": "synthetic_dependency_topology_with_competing_evidence",
        "size": size, "rows": rows, "network_calls": 0, "model_calls": 0,
        "limitations": ["synthetic declared dependency graphs", "not evidence of real-world semantic completeness"],
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--size", type=int, default=8)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    report = run(args.size)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

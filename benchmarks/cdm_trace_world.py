"""Deterministic multi-agent trace worlds with independent provenance truth."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class TraceEvent:
    event_id: str
    sequence: int
    kind: str
    agent_id: str | None
    source_id: str | None
    source_root: str | None
    value: str | None
    visible_sources: tuple[str, ...]


def shared_source_world(*, agent_count: int, seed: int) -> dict[str, Any]:
    if type(agent_count) is not int or agent_count not in {2, 3, 10, 50}:
        raise ValueError("agent_count must be 2, 3, 10 or 50")
    random.Random(seed)  # Validate and bind seed as part of the generator contract.
    root = f"source-{seed}-root"
    events = [TraceEvent("source", 1, "source", None, root, root, "alarm", ())]
    for index in range(agent_count):
        agent = f"agent-{index:02d}"
        copy_id = f"copy-{index:02d}"
        events.append(TraceEvent(f"copy-event-{index:02d}", index + 2, "copy", agent,
                                 copy_id, root, "alarm", (root,)))
        events.append(TraceEvent(f"decision-{index:02d}", index + 2, "decision", agent,
                                 None, None, None, (root, copy_id)))
    ordered = tuple(sorted(events, key=lambda event: (event.sequence, event.event_id)))
    return _manifest("shared-source", agent_count, seed, ordered,
                     {f"copy-{index:02d}": root for index in range(agent_count)})


def temporal_conflict_world(*, seed: int) -> dict[str, Any]:
    events = (TraceEvent("initial", 1, "source", None, "sensor-a", "root-a", "high", ()),
              TraceEvent("decision-1", 2, "decision", "agent-a", None, None, None,
                         ("sensor-a",)),
              TraceEvent("conflict", 3, "correction", None, "sensor-b", "root-b", "low", ()),
              TraceEvent("decision-2", 4, "decision", "agent-a", None, None, None,
                         ("sensor-a", "sensor-b")))
    return _manifest("conflict-after-decision", 1, seed, events,
                     {"sensor-a": "root-a", "sensor-b": "root-b"})


def delayed_retraction_world(*, agent_count: int, seed: int) -> dict[str, Any]:
    world = shared_source_world(agent_count=agent_count, seed=seed)
    events = list(world["events"])
    last = max(event.sequence for event in events)
    events.append(TraceEvent("retraction", last + 1, "retraction", None,
                             f"source-{seed}-root", f"source-{seed}-root", "withdrawn", ()))
    # Offline peers retain prior local visibility until their explicit sync event.
    events.append(TraceEvent("peer-sync", last + 2, "sync", "agent-00",
                             f"source-{seed}-root", f"source-{seed}-root", None, ()))
    events = [event if event.event_id != "peer-sync" else
              TraceEvent(event.event_id, event.sequence, event.kind, event.agent_id,
                         event.source_id, event.source_root, event.value, ()) for event in events]
    return _manifest("delayed-retraction", agent_count, seed,
                     tuple(sorted(events, key=lambda event: (event.sequence, event.event_id))),
                     world["source_roots"])


def negative_control_world(*, seed: int) -> dict[str, Any]:
    """One compact trace per named control; repeated/copy values share a root."""
    events = (
        TraceEvent("source-a", 1, "source", None, "a", "root-a", "alarm", ()),
        TraceEvent("decision-a", 2, "decision", "agent-a", None, None, None, ("a",)),
        TraceEvent("irrelevant", 3, "irrelevant", None, "weather", "root-weather",
                    "sunny", ()),
        TraceEvent("duplicate", 4, "duplicate", "agent-a", "a-copy", "root-a",
                    "alarm", ("a",)),
        TraceEvent("correlated-copy", 5, "copy", "agent-b", "a-copy-2", "root-a",
                    "alarm", ("a", "a-copy")),
        TraceEvent("delayed", 6, "delayed", "agent-b", "late", "root-late",
                    "late-signal", ()),
        TraceEvent("policy-swap", 7, "policy_swap", "agent-a", None, None,
                    "policy-v2", ("a",)),
    )
    roots = {"a": "root-a", "a-copy": "root-a", "a-copy-2": "root-a",
             "weather": "root-weather", "late": "root-late"}
    return _manifest("negative-controls", 2, seed, events, roots)


def independent_source_root(world: dict[str, Any], source_id: str) -> str | None:
    """Oracle truth comes only from generator provenance, not CDM graph code."""
    for event in world["events"]:
        if event.source_id == source_id and event.source_root is not None:
            return event.source_root
    return None


def _manifest(world_id: str, agent_count: int, seed: int, events: tuple[TraceEvent, ...],
              roots: dict[str, str]) -> dict[str, Any]:
    rows = [asdict(event) for event in events]
    digest = hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(",", ":"))
                            .encode("utf-8")).hexdigest()
    return {"schema": "cdm-trace-world-v1", "world": world_id, "agent_count": agent_count,
            "seed": seed, "events": events, "source_roots": roots,
            "workload_sha256": digest, "remote_calls": 0}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=20261108)
    parser.add_argument("--out", default="")
    args = parser.parse_args()
    worlds = [shared_source_world(agent_count=count, seed=args.seed)
              for count in (2, 3, 10, 50)]
    worlds += [temporal_conflict_world(seed=args.seed),
               delayed_retraction_world(agent_count=3, seed=args.seed),
               negative_control_world(seed=args.seed)]
    rendered = json.dumps([{**world, "events": [asdict(event) for event in world["events"]]}
                           for world in worlds], sort_keys=True, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as stream:
            stream.write(rendered + "\n")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

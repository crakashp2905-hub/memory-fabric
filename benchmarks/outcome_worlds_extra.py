"""Temporal-validity and multi-hop world families (W05-07, W05-09).

    python -m benchmarks.outcome_worlds_extra --seeds 4

**Temporal validity.** A limit was A until time T and is B from T on. Those two
claims do not contradict each other; they hold at different valid times. Each
world asks two questions: the historical fact at a time before T, and the value
an action taken now must use. The oracle knows both. Policies:

``temporal``        picks the claim whose valid interval contains the question time
``timeless``        treats differing claims as a contradiction and abstains
``latest_known``    takes the claim recorded last, whatever its valid time

**Multi-hop.** A unit is wired to a pump, and the pump has a relief limit. The
answer needs both records, and later the unit is re-wired to another pump (the
old wiring is withdrawn). Policies:

``two_hop``         resolves the unit's current pump, then that pump's limit
``single_record``   answers from the one record that best matches the question
``exact_match``     answers from a record containing the unit id verbatim

Everything runs on a real Memory Fabric store. The oracle answer is set by
construction and never passed to a policy.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any, Callable, Mapping, Sequence

SCHEMA_ID = "memory-fabric.agent-outcome-extra-worlds.v1"
NUMBER = re.compile(r"(\d+) bar")
PUMP = re.compile(r"pump (P-\d+)")


def _value(text: str) -> int | None:
    match = NUMBER.search(text)
    return int(match.group(1)) if match else None


# --- temporal validity -------------------------------------------------------------------


def temporal_world(seed: int) -> dict[str, Any]:
    from memory_fabric import MemoryFabric

    fabric = MemoryFabric(":memory:", auto_activate=True)
    switch = 100 + seed
    before, after = 10 + seed, 20 + seed
    valve = f"V-{seed:03d}"
    old = fabric.remember("ana", f"valve {valve} pressure limit is {before} bar", scope="team",
                          valid_from=0, valid_to=switch)
    new = fabric.remember("ana", f"valve {valve} pressure limit is {after} bar", scope="team",
                          valid_from=switch, valid_to=None)
    return {"fabric": fabric, "valve": valve, "switch": switch, "ids": (old, new),
            "questions": [{"kind": "historical", "at": switch - 50, "answer": before},
                          {"kind": "action_now", "at": switch + 50, "answer": after}]}


def _candidates(fabric: Any, query: str) -> list[dict[str, Any]]:
    out = []
    for item in fabric.retrieve(agent_id="ops", query=query, k=5, method="lexical"):
        memory_id = str(getattr(item, "memory_id", None) or getattr(item, "id"))
        memory = fabric.get(memory_id)
        out.append({"id": memory_id, "text": memory.content, "valid_from": memory.valid_from,
                    "valid_to": memory.valid_to, "recorded": memory.created_at})
    return out


def policy_temporal(candidates: Sequence[Mapping[str, Any]], at: int) -> int | None:
    live = [c for c in candidates
            if (c["valid_from"] is None or c["valid_from"] <= at)
            and (c["valid_to"] is None or at < c["valid_to"])]
    values = {_value(c["text"]) for c in live} - {None}
    return values.pop() if len(values) == 1 else None


def policy_timeless(candidates: Sequence[Mapping[str, Any]], at: int) -> int | None:
    values = {_value(c["text"]) for c in candidates} - {None}
    return values.pop() if len(values) == 1 else None  # differing claims -> abstain


def policy_latest_known(candidates: Sequence[Mapping[str, Any]], at: int) -> int | None:
    if not candidates:
        return None
    return _value(max(candidates, key=lambda c: (c["recorded"], c["id"]))["text"])


TEMPORAL_POLICIES: Mapping[str, Callable[[Sequence[Mapping[str, Any]], int], int | None]] = {
    "temporal": policy_temporal, "timeless": policy_timeless, "latest_known": policy_latest_known,
}


def run_temporal(seeds: int) -> dict[str, Any]:
    rows = []
    for seed in range(seeds):
        world = temporal_world(seed)
        try:
            candidates = _candidates(world["fabric"], f"valve {world['valve']} pressure limit")
            for question in world["questions"]:
                for name, policy in TEMPORAL_POLICIES.items():
                    answer = policy(candidates, question["at"])
                    rows.append({"seed": seed, "question": question["kind"], "policy": name,
                                 "answer": answer, "correct": answer == question["answer"]})
        finally:
            world["fabric"].close()
    return _summary(rows, "question")


# --- multi-hop --------------------------------------------------------------------------


def multihop_world(seed: int) -> dict[str, Any]:
    from memory_fabric import MemoryFabric

    fabric = MemoryFabric(":memory:", auto_activate=True)
    unit, first, second = f"U-{seed:03d}", f"P-{100 + seed}", f"P-{200 + seed}"
    first_limit, second_limit = 30 + seed, 40 + seed
    wiring = fabric.remember("ana", f"unit {unit} is wired to pump {first}", scope="team")
    fabric.remember("ana", f"pump {first} relief limit is {first_limit} bar", scope="team")
    fabric.remember("ana", f"pump {second} relief limit is {second_limit} bar", scope="team")
    # A distractor that shares the question's words but answers nothing about this unit.
    fabric.remember("ana", f"unit {unit} relief limit review is scheduled; legacy note says "
                           f"{first_limit + 7} bar", scope="team")
    return {"fabric": fabric, "unit": unit, "wiring": wiring, "second": second,
            "answers": {"before": first_limit, "after": second_limit}}


def rewire(world: Mapping[str, Any]) -> None:
    fabric = world["fabric"]
    fabric.quarantine(world["wiring"], reason="unit re-wired", actor="ops")
    fabric.remember("ana", f"unit {world['unit']} is wired to pump {world['second']}", scope="team")


def policy_two_hop(fabric: Any, unit: str) -> int | None:
    wiring = [c for c in _candidates(fabric, f"unit {unit} wired to pump")
              if f"unit {unit} is wired to" in c["text"]]
    pumps = {m.group(1) for c in wiring if (m := PUMP.search(c["text"]))}
    if len(pumps) != 1:
        return None
    pump = pumps.pop()
    limits = {_value(c["text"]) for c in _candidates(fabric, f"pump {pump} relief limit")
              if c["text"].startswith(f"pump {pump} relief limit")} - {None}
    return limits.pop() if len(limits) == 1 else None


def policy_single_record(fabric: Any, unit: str) -> int | None:
    found = _candidates(fabric, f"unit {unit} relief limit")
    return _value(found[0]["text"]) if found else None


def policy_exact_match(fabric: Any, unit: str) -> int | None:
    for candidate in _candidates(fabric, unit):
        if unit in candidate["text"] and _value(candidate["text"]) is not None:
            return _value(candidate["text"])
    return None


MULTIHOP_POLICIES: Mapping[str, Callable[[Any, str], int | None]] = {
    "two_hop": policy_two_hop, "single_record": policy_single_record,
    "exact_match": policy_exact_match,
}


def run_multihop(seeds: int) -> dict[str, Any]:
    rows = []
    for seed in range(seeds):
        world = multihop_world(seed)
        try:
            for phase in ("before", "after"):
                if phase == "after":
                    rewire(world)
                for name, policy in MULTIHOP_POLICIES.items():
                    answer = policy(world["fabric"], world["unit"])
                    rows.append({"seed": seed, "phase": phase, "policy": name, "answer": answer,
                                 "correct": answer == world["answers"][phase]})
        finally:
            world["fabric"].close()
    return _summary(rows, "phase")


def _summary(rows: Sequence[Mapping[str, Any]], split: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for policy in sorted({r["policy"] for r in rows}):
        mine = [r for r in rows if r["policy"] == policy]
        out[policy] = {"accuracy": round(sum(r["correct"] for r in mine) / len(mine), 4),
                       "by_" + split: {key: round(sum(r["correct"] for r in mine if r[split] == key)
                                                  / len([r for r in mine if r[split] == key]), 4)
                                       for key in sorted({r[split] for r in mine})}}
    return {"policies": out, "rows": list(rows)}


def run(seeds: int = 4) -> dict[str, Any]:
    return {"schema_id": SCHEMA_ID, "population": "SCRIPTED_DEVELOPMENT", "seeds": seeds,
            "temporal_validity": run_temporal(seeds), "multi_hop": run_multihop(seeds)}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seeds", type=int, default=4)
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    report = run(args.seeds)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(report, indent=1, sort_keys=True) + "\n")
    for family in ("temporal_validity", "multi_hop"):
        print(family, {k: v["accuracy"] for k, v in report[family]["policies"].items()})
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

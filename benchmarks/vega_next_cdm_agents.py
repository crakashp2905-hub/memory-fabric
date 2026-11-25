"""Does dependence-first replay add net utility when a learned model makes the decisions? (freeze F07-05)

    python -m benchmarks.vega_next_cdm_agents --seeds 40 --seed-offset 100 --model qwen2.5:1.5b \\
        --host http://127.0.0.1:11434 --out research/results/vega-cdm/freeze/ladder/S2-cdm-agents-seeds100-139.json

The worlds are the scripted CDM worlds (``benchmarks.vega_next_cdm_value.world``): six packs,
each initially hot or not; a correction then flips some packs. A pinned local chat model makes
every pack decision from the pack's evidence line ("pack P3 reads 61 C at 10:00"), choosing
``diagnose`` or ``monitor``. After the correction the arms differ only in which decisions are
asked again:

``no_replay``   none                          ``full_replan``  every pack
``dependence``  the packs whose evidence changed  ``oracle``     the packs whose correct action changed

Utility per task = decisions that end correct - ``cost`` x re-asked decisions. Every model call
is recorded; a failed call is a wrong decision, never dropped. The grader reads only the
world's corrected flags, never the model.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from typing import Any, Sequence

from memory_fabric.adapters.ollama import OllamaClient

from .vega_next_cdm_value import world

ARMS = ("no_replay", "full_replan", "dependence", "oracle")
SYSTEM = ("You decide what to do with one battery pack. Reply with JSON {\"action\": \"diagnose\"} if the pack "
          "reads above 50 C, otherwise {\"action\": \"monitor\"}. Reply with the JSON object only.")
SCHEMA = {"type": "object", "properties": {"action": {"type": "string", "enum": ["diagnose", "monitor"]}},
          "required": ["action"]}


def evidence(pack: str, hot: bool, seed: int, version: int) -> str:
    reading = 58 + (seed + int(pack[1:])) % 9 if hot else 31 + (seed * 3 + int(pack[1:])) % 15
    return f"pack {pack} reads {reading} C at {10 + version}:00"


class Decider:
    def __init__(self, client: OllamaClient, model: str) -> None:
        self.client, self.model, self.calls, self.failures, self.seconds = client, model, 0, 0, 0.0
        self.cache: dict[str, str | None] = {}

    def __call__(self, text: str) -> str | None:
        if text in self.cache:  # identical prompt, temperature 0: the same answer, not a new call
            return self.cache[text]
        self.calls += 1
        t0 = time.perf_counter()
        try:
            reply = self.client.chat(self.model, [{"role": "system", "content": SYSTEM},
                                                  {"role": "user", "content": text}],
                                     temperature=0.0, num_predict=16, schema=SCHEMA, seed=0)
            action = json.loads(reply.get("message", {}).get("content", "")).get("action")
            action = action if action in ("diagnose", "monitor") else None
        except Exception:  # noqa: BLE001 - a failed call is a wrong decision, kept in the denominator
            action = None
        self.seconds += time.perf_counter() - t0
        if action is None:
            self.failures += 1
        self.cache[text] = action
        return action


def run_task(seed: int, decide: Decider, cost: float) -> list[dict[str, Any]]:
    w = world(seed)
    packs = sorted(w["initial"])
    truth = {p: "diagnose" if w["corrected"][p] else "monitor" for p in packs}
    first = {p: decide(evidence(p, w["initial"][p], seed, 0)) for p in packs}
    rows = []
    for arm in ARMS:
        if arm == "no_replay":
            chosen: list[str] = []
        elif arm == "full_replan":
            chosen = packs
        elif arm == "dependence":
            chosen = sorted(w["changed"])
        else:
            chosen = [p for p in packs if truth[p] != first[p]]
        final = dict(first)
        for p in chosen:
            final[p] = decide(evidence(p, w["corrected"][p], seed, 1))
        correct = sum(final[p] == truth[p] for p in packs)
        rows.append({"arm": arm, "seed": seed, "decisions": len(packs), "replays": len(chosen),
                     "correct": correct, "stale": sum(final[p] != truth[p] for p in w["changed"]),
                     "utility": round(correct - cost * len(chosen), 4)})
    return rows


def run(seeds: Sequence[int], client: OllamaClient, model: str, cost: float = 0.25) -> dict[str, Any]:
    decide = Decider(client, model)
    rows = [r for s in seeds for r in run_task(s, decide, cost)]
    summary = {}
    for arm in ARMS:
        mine = [r for r in rows if r["arm"] == arm]
        summary[arm] = {"tasks": len(mine), "decisions": sum(r["decisions"] for r in mine),
                        "correct": sum(r["correct"] for r in mine), "replays": sum(r["replays"] for r in mine),
                        "stale": sum(r["stale"] for r in mine), "net_utility": round(sum(r["utility"] for r in mine), 2)}
    best = max(("full_replan", "no_replay"), key=lambda a: summary[a]["net_utility"])
    return {"schema_id": "memory-fabric.vega-next-cdm-agents.v1", "seeds": list(seeds), "replay_cost": cost,
            "model": model, "model_calls": decide.calls, "model_failures": decide.failures,
            "model_seconds": round(decide.seconds, 1), "summary": summary, "strongest_fair_comparator": best,
            "dependence_minus_strongest": round(summary["dependence"]["net_utility"] - summary[best]["net_utility"], 2),
            "system_prompt_sha256": hashlib.sha256(SYSTEM.encode()).hexdigest(),
            "scope": "learned local planner on recorded correction worlds; replay re-asks the same pinned model",
            "rows": rows}


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--seeds", type=int, default=40)
    p.add_argument("--seed-offset", type=int, default=100)
    p.add_argument("--model", default="qwen2.5:1.5b")
    p.add_argument("--host", default="http://127.0.0.1:11434")
    p.add_argument("--cost", type=float, default=0.25)
    p.add_argument("--out")
    args = p.parse_args(argv)
    client = OllamaClient(args.host)
    report = run(range(args.seed_offset, args.seed_offset + args.seeds), client, args.model, args.cost)
    import urllib.request
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    report["agent_model_tags"] = json.loads(opener.open(args.host + "/api/tags", timeout=10).read())["models"]
    report["evidence_level"] = "LOCAL_MODEL_DEVELOPMENT"
    if args.out:
        import os
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(report, indent=1, sort_keys=True) + "\n")
    print(json.dumps({"summary": report["summary"], "strongest": report["strongest_fair_comparator"],
                      "gain": report["dependence_minus_strongest"], "calls": report["model_calls"]}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())

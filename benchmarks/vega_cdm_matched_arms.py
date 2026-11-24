"""Matched semantic-CDM arms on the seeded worlds (VEGA S12).

    python -m benchmarks.vega_cdm_matched_arms --seeds 8 --out research/results/vega-cdm/development/scripted.json
    python -m benchmarks.vega_cdm_matched_arms --seeds 8 --advisor vega --vega-url http://127.0.0.1:8011 \\
        --out research/results/vega-cdm/development/vega-0.8b.json

Arms (frozen A-ids keep their meaning; ``-V`` suffixes are new):

``A3``   pooled memory with retraction recheck: sees every tenant, counts copies as sources.
``A5``   governed packets: current tenant only, source roots deduplicated, exact parser.
``A5-V`` A5 plus the semantic advisor, asked only about packets the exact parser cannot read.
``A6``   A5 plus dependence-first counterfactual dispatch on changed evidence.
``A6-V`` A5-V plus the same dispatch.
``A7``   the oracle: same k and budget, knows the hidden truth. No arm may beat it.

Every arm gets the same world, the same retrieval ``k`` and the same decision rule
(:func:`decide`); only the evidence view and the advisor differ (VEGA-CDM-122,
128). The run manifest records the advisor's evidence level: with the scripted
advisor the ``-V`` arms are ``SCRIPTED`` and say nothing about Vega.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from typing import Any, Mapping, Sequence

from memory_fabric.causal_replay.semantic import packets
from memory_fabric.causal_replay.semantic.advice import Advisor, Question
from memory_fabric.causal_replay.semantic.support import exact_guard

from . import vega_cdm_worlds as worlds

ARMS = ("A3", "A5", "A5-V", "A6", "A6-V", "A7")
K = 12
ADVISOR_CALL_BUDGET = 8
_READ = re.compile(r"sensor T([AB])[12] reads (\d+) C")
QUESTIONS = {
    "sensor": Question("sensor", "choice", "Which sensor on pack P-7 does this evidence report?",
                       {"probe_a": "sensor TA1, the A-side thermistor", "probe_b": "sensor TB2, the second sensor",
                        "neither": "no pack P-7 sensor reading, or another pack"}),
    "hot": Question("hot", "boolean", "Does this evidence report a pack P-7 temperature above 50 degrees Celsius?",
                    {"true": "a reading above 50 C", "false": "a reading at or below 50 C, or no reading"}),
    "doubt": Question("doubt", "boolean",
                      "Does this evidence say sensor TA1 may be miscalibrated or overdue for calibration?",
                      {"true": "calibration is doubtful", "false": "no calibration doubt"}),
}


def parse_exact(text: str) -> dict[str, Any] | None:
    """The deterministic reader: canonical readings and notes only."""
    if "P-7" not in text:
        return None
    m = _READ.search(text)
    if m:
        return {"probe": m.group(1).lower(), "hot": int(m.group(2)) > 50}
    if "calibration overdue" in text:
        return {"doubt": True}
    if "coolant leak" in text:
        return {"leak": " no coolant leak" not in text}
    return None


def parse_semantic(text: str, advisor: Advisor, meter: dict[str, Any]) -> dict[str, Any] | None:
    if meter["calls"] >= ADVISOR_CALL_BUDGET or exact_guard("pack P-7", text) == "incomparable":
        return None
    meter["calls"] += 1
    t0 = time.perf_counter()
    advice = advisor.decide(f"Evidence: {text}", QUESTIONS)
    meter["seconds"] += time.perf_counter() - t0
    meter["levels"].add(str(advice.receipt.get("evidence_level")))
    a = advice.answers
    if a["doubt"].decisive and a["doubt"].value is not None and float(a["doubt"].value) > 0.5:
        return {"doubt": True}
    sensor, hot = a["sensor"], a["hot"]
    if sensor.decisive and hot.decisive and sensor.value in ("probe_a", "probe_b"):
        return {"probe": sensor.value[-1], "hot": float(hot.value) > 0.5}
    meter["undecided"] += 1
    return None


def decide(signals: Sequence[tuple[str, Mapping[str, Any]]]) -> str:
    """One rule for every arm. ``signals`` are (source key, parsed signal); sources are what count."""
    leak = {s for s, x in signals if x.get("leak") is True}
    no_leak = {s for s, x in signals if x.get("leak") is False}
    if leak or no_leak:
        if len(leak) >= 2 and len(leak) > len(no_leak):
            return "isolate_pack"
        if len(no_leak) >= 2 and len(no_leak) > len(leak):
            return "no_action"
        return "abstain"
    reads: dict[str, set[bool]] = {"a": set(), "b": set()}
    doubt = False
    for _, x in signals:
        if "probe" in x:
            reads[x["probe"]].add(bool(x["hot"]))
        doubt = doubt or bool(x.get("doubt"))
    if any(len(v) > 1 for v in reads.values()) or not reads["a"] or not reads["b"]:
        return "abstain"
    a_hot, b_hot = next(iter(reads["a"])), next(iter(reads["b"]))
    if a_hot and b_hot:
        return "cool_and_recalibrate" if doubt else "cool_pack"
    if a_hot and not b_hot:
        return "recalibrate_probe" if doubt else "abstain"
    if not a_hot and not b_hot and not doubt:
        return "no_action"
    return "abstain"


def _pooled_signals(fabric: Any) -> list[tuple[str, Mapping[str, Any]]]:
    out: list[tuple[str, Mapping[str, Any]]] = []
    for mid, memory in sorted(fabric.state.memories.items()):
        state = getattr(memory.lifecycle_state, "value", "")
        if state in ("deprecated", "quarantined", "deleted"):
            continue
        parsed = parse_exact(memory.content)
        if parsed:
            out.append((mid, parsed))  # every memory is its own source: copies count
    return out


def _governed_signals(fabric: Any, world: worlds.World, advisor: Advisor | None,
                      meter: dict[str, Any]) -> tuple[list[tuple[str, Mapping[str, Any]]], packets.PacketBundle]:
    bundle = packets.from_retrieval(fabric, "planner", world.query, tenant_id=worlds.TENANT, k=K)
    bundle = packets.recheck(fabric, bundle, agent_id="planner", tenant_id=worlds.TENANT)
    out: list[tuple[str, Mapping[str, Any]]] = []
    for p in bundle.packets:
        parsed = parse_exact(p.visible_text)
        if parsed is None and advisor is not None:
            parsed = parse_semantic(p.visible_text, advisor, meter)
        if parsed:
            out.append((p.origin_root, parsed))
    return out, bundle


def run_arm(arm: str, world: worlds.World, advisor: Advisor | None) -> dict[str, Any]:
    fabric = worlds.materialize(world)
    meter: dict[str, Any] = {"calls": 0, "seconds": 0.0, "levels": set(), "undecided": 0}
    cdm = {"replays": 0, "skipped_independent": 0, "flips": 0}
    try:
        if arm == "A7":
            action = world.correct
        elif arm == "A3":
            action = decide(_pooled_signals(fabric))
        else:
            use = advisor if arm.endswith("-V") else None
            signals, bundle = _governed_signals(fabric, world, use, meter)
            action = decide(signals)
            if arm.startswith("A6"):
                changed = [p for p in bundle.packets if p.version > 1]
                if not changed:
                    cdm["skipped_independent"] = 1
                else:  # replay the decision without each changed input: does it depend on it?
                    for p in changed:
                        cdm["replays"] += 1
                        if decide([s for s in signals if s[0] != p.origin_root]) != action:
                            cdm["flips"] += 1
    finally:
        fabric.close()
    graded = worlds.grade(world, action)
    return {"arm": arm, "family": world.family, "seed": world.seed, "task_id": world.task_id,
            "action": action, **graded, "advisor_calls": meter["calls"],
            "advisor_seconds": round(meter["seconds"], 3), "advisor_undecided": meter["undecided"],
            "advisor_levels": sorted(meter["levels"]), "cdm": cdm}


def summarize(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for arm in ARMS:
        mine = [r for r in rows if r["arm"] == arm]
        if not mine:
            continue
        n = len(mine)
        out[arm] = {"tasks": n, "safe_success": round(sum(r["safe_success"] for r in mine) / n, 4),
                    "unsafe": sum(r["unsafe"] for r in mine), "abstained": sum(r["abstained"] for r in mine),
                    "advisor_calls": sum(r["advisor_calls"] for r in mine),
                    "advisor_seconds": round(sum(r["advisor_seconds"] for r in mine), 2),
                    "by_family": {f: round(sum(r["safe_success"] for r in mine if r["family"] == f)
                                           / max(1, sum(1 for r in mine if r["family"] == f)), 4)
                                  for f in sorted({r["family"] for r in mine})}}
    oracle = out.get("A7", {}).get("safe_success")
    out["ceiling_check"] = ("NO_ARM_ABOVE_ORACLE" if oracle is not None and all(
        v["safe_success"] <= oracle for k, v in out.items() if isinstance(v, dict) and "safe_success" in v)
        else "ARM_ABOVE_ORACLE: the ceiling is wrong")
    return out


def run(seeds: int, advisor: Advisor | None, advisor_level: str,
        families: Sequence[str] = worlds.FAMILIES) -> dict[str, Any]:
    rows = [run_arm(arm, worlds.build(f, s), advisor) for f in families for s in range(seeds) for arm in ARMS]
    pairs = {}
    for f in families:
        for s in range(seeds):
            by = {r["arm"]: r for r in rows if r["family"] == f and r["seed"] == s}
            pairs[f"{f}:{s}"] = {c: int(by[c.split("-minus-")[0]]["safe_success"])
                                 - int(by[c.split("-minus-")[1]]["safe_success"])
                                 for c in ("A5-V-minus-A5", "A5-V-minus-A3", "A6-V-minus-A5-V", "A6-minus-A5")}
    contrasts = {c: round(sum(p[c] for p in pairs.values()) / len(pairs), 4)
                 for c in ("A5-V-minus-A5", "A5-V-minus-A3", "A6-V-minus-A5-V", "A6-minus-A5")}
    digest = hashlib.sha256(json.dumps(rows, sort_keys=True, default=str).encode()).hexdigest()
    return {"schema_id": "memory-fabric.vega-cdm-matched-arms.v1", "split": "development",
            "evidence_level": advisor_level, "seeds": seeds, "families": list(families), "k": K,
            "advisor_call_budget": ADVISOR_CALL_BUDGET, "summary": summarize(rows), "contrasts": contrasts,
            "verdict": "DEVELOPMENT_ONLY: no registered confirmatory test", "rows_digest": digest, "rows": rows}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seeds", type=int, default=8)
    parser.add_argument("--advisor", choices=("scripted", "vega", "none"), default="scripted")
    parser.add_argument("--vega-url", default="http://127.0.0.1:8011")
    parser.add_argument("--families", nargs="*", default=list(worlds.FAMILIES))
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    advisor: Advisor | None
    if args.advisor == "vega":
        from memory_fabric.adapters.vega_u import VegaClient
        advisor, level = VegaClient(args.vega_url), "VEGA_MODEL_DEVELOPMENT"
    elif args.advisor == "scripted":
        from memory_fabric.causal_replay.semantic.scripted import ScriptedAdvisor
        advisor, level = ScriptedAdvisor(), "SCRIPTED"
    else:
        advisor, level = None, "NO_ADVISOR"
    report = run(args.seeds, advisor, level, args.families)
    handshake = getattr(advisor, "handshake", None)
    if args.advisor == "vega" and handshake is not None:
        report["model"] = handshake()
    if args.out:
        import os
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(report, sort_keys=True, indent=1, default=sorted) + "\n")
    print(json.dumps({"summary": {k: (v["safe_success"] if isinstance(v, dict) else v)
                                  for k, v in report["summary"].items()}, "contrasts": report["contrasts"]},
                     indent=1))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

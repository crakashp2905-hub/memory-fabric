"""Fair matched arms for the next Vega study, isolating parser, guard, model and CDM (VEGA next W11).

    python -m benchmarks.vega_next_arms --split dev --seeds 8 --advisor scripted --out ...
    python -m benchmarks.vega_next_arms --split dev --seeds 8 --advisor vega --out ...

Established arm ids keep their meaning (``A3``, ``A5``, ``A5-V``, ``A6``, ``A6-V``, ``A7`` are the
PR #41 pipelines, run unchanged on the new worlds, W11-01). New arms add one component each:

``A3-P``     pooled memory with the typed parser: the cheap baseline any gain must beat (W11-03)
``A5-P``     governed packets + typed observations + deterministic doubt rule + omission guard
``A5-PnoG``  A5-P without the omission guard (isolates the guard)
``A5-PV``    A5-P + vega-U, asked only whether a TA1 note casts doubt on it or clears it, when the
             typed readings leave exactly that open (hybrid verifier + model, W11-04)
``A5-VG``    the PR #41 A5-V pipeline + the omission guard
``A5-PV-shuffled``   A5-PV with the advisor shown another task's note (placebo, W11-07)
``A5-PV-wrongconf``  A5-PV with the advisor's probability inverted (placebo)
``A6-P`` / ``A6-PV``  dependence-first replay over changed evidence on top of A5-P / A5-PV
``A7``       the oracle: same retrieval, knows the hidden truth

Every arm sees the same world, the same retrieval ``k`` and the same model-call budget, and
the actual consumption is recorded per row (W11-05). Rows report completion, justified
abstention, false withholding, unsafe omission and unsafe execution separately (W11-06).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
import time
from typing import Any, Mapping, Sequence

from memory_fabric.causal_replay.semantic import packets
from memory_fabric.causal_replay.semantic.advice import Advisor, Question
from memory_fabric.causal_replay.semantic.entities import battery_registry
from memory_fabric.causal_replay.semantic.observations import Predicate
from memory_fabric.causal_replay.semantic.verified_observations import Verification, verify
from memory_fabric.outcome_typed.omission import HazardPolicy, assess, guard, terminal_action

from . import vega_cdm_matched_arms as old
from . import vega_next_worlds as worlds

ARMS = ("A3", "A3-P", "A5", "A5-V", "A5-VG", "A5-P", "A5-PnoG", "A5-PV", "A5-PV-shuffled", "A5-PV-wrongconf",
        "A6-P", "A6-PV", "A7")
K = 16
CALL_BUDGET = 8
TA1, TB2 = "pack:p-7/sensor:ta1", "pack:p-7/sensor:tb2"
POLICY = HazardPolicy("pack-p7-overheat", (TA1, TB2), response=frozenset({"cool_pack", "cool_and_recalibrate"}))
HOT = Predicate("temperature", "gt", 50.0)
REGISTRY = battery_registry()
# Written from the development templates only; holdout phrasing is deliberately different.
DOUBT_RULE = re.compile(r"calibration overdue|not been checked against a reference|drift possible", re.I)
CLEAR_RULE = re.compile(r"checked against the reference this week: accurate|verified against a reference meter "
                        r"yesterday, within tolerance", re.I)
DOUBT_Q = {"doubt": Question("doubt", "boolean",
                             "Does this note say sensor TA1 (the A-side thermistor) may be inaccurate, miscalibrated "
                             "or overdue for a calibration check?",
                             {"true": "TA1's accuracy is in doubt", "false": "no doubt about TA1's accuracy"}),
           "cleared": Question("cleared", "boolean",
                               "Does this note say sensor TA1 (the A-side thermistor) was recently checked or "
                               "replaced and is accurate?",
                               {"true": "TA1 was recently verified accurate", "false": "no such verification"})}


def typed_decision(v: Verification, doubt: Any) -> str:
    """The shared decision rule on verified findings; unknown or contested readings abstain.

    ``doubt`` is "yes" (TA1 may be inaccurate), "cleared" (TA1 was verified accurate) or None.
    A bare ``True``/``False`` is read as "yes"/None for compatibility.
    """
    state = "yes" if doubt is True else (None if doubt is False else doubt)
    a, b = v.findings.get(TA1), v.findings.get(TB2)
    if not a or not b or a.status != "VERIFIED" or b.status != "VERIFIED":
        return "abstain"
    a_hot, b_hot = a.value == "TRUE", b.value == "TRUE"
    if a_hot and b_hot:
        return "cool_and_recalibrate" if state == "yes" else "cool_pack"
    if a_hot and not b_hot:
        return {"yes": "recalibrate_probe", "cleared": "cool_pack"}.get(state or "", "abstain")
    if not a_hot and not b_hot and state != "yes":
        return "no_action"
    return "abstain"


def rule_doubt(texts: Sequence[str]) -> str | None:
    """The deterministic reading of notes, written from development phrasing only."""
    if any(DOUBT_RULE.search(t) for t in texts):
        return "yes"
    if any(CLEAR_RULE.search(t) for t in texts):
        return "cleared"
    return None


def _notes(bundle: packets.PacketBundle) -> list[packets.SemanticEvidencePacket]:
    """Packets about TA1 that carry no reading: where a calibration doubt could be."""
    from memory_fabric.causal_replay.semantic.observations import extract
    out = []
    for p in bundle.packets:
        if REGISTRY.resolve(p.visible_text).canonical == TA1 and not extract(p.visible_text, default_unit="C"):
            out.append(p)
    return out


def _ask_doubt(text: str, advisor: Advisor, meter: dict[str, Any], invert: bool = False,
               acceptance: Mapping[str, float] | None = None) -> str | None:
    """"yes", "cleared" or None from vega-U's two answers about one note.

    Default rule: accept one answer only when the other is not also yes. With ``acceptance``
    (a dev-fitted margin, benchmarks.vega_margin_fit) the decision is on p(doubt) - p(cleared):
    above ``doubt_margin_above`` is "yes", below ``cleared_margin_below`` is "cleared"
    (freeze plan F05-03). The same rule applies to the real arm and to both placebos.
    """
    if meter["calls"] >= CALL_BUDGET:
        meter["over_budget"] += 1
        return None
    meter["calls"] += 1
    t0 = time.perf_counter()
    advice = advisor.decide(f"Note: {text}", DOUBT_Q)
    meter["seconds"] += time.perf_counter() - t0
    meter["levels"].add(str(advice.receipt.get("evidence_level")))
    got = {}
    for q in ("doubt", "cleared"):
        ans = advice.answers[q]
        p = float(ans.value) if ans.decisive and ans.value is not None else None
        got[q] = None if p is None else ((1 - p) if invert else p) > 0.5
        meter.setdefault("trace", []).append({"text": text, "question": q, "status": ans.status, "p_true": ans.value,
                                              "prediction_set": list(ans.prediction_set)})
    if acceptance is not None:
        pd = advice.answers["doubt"]
        pc = advice.answers["cleared"]
        if not (pd.decisive and pc.decisive and pd.value is not None and pc.value is not None):
            return None
        margin = float(pd.value) - float(pc.value)
        if invert:
            margin = -margin
        if margin > acceptance["doubt_margin_above"]:
            return "yes"
        if margin < acceptance["cleared_margin_below"]:
            return "cleared"
        return None
    if got["doubt"] is True and got["cleared"] is not True:
        return "yes"
    if got["cleared"] is True and got["doubt"] is not True:
        return "cleared"
    return None


def run_arm(arm: str, world: worlds.World, advisor: Advisor | None, *, placebo_texts: Sequence[str] = (),
            acceptance: Mapping[str, float] | None = None) -> dict[str, Any]:
    fabric = worlds.materialize(world)
    meter: dict[str, Any] = {"calls": 0, "seconds": 0.0, "levels": set(), "over_budget": 0}
    detail: dict[str, Any] = {}
    try:
        if arm == "A7":
            action = world.correct
        elif arm in ("A3", "A5", "A5-V", "A5-VG"):
            # PR #41 pipelines unchanged, on the new worlds.
            if arm == "A3":
                action = old.decide(old._pooled_signals(fabric))
            else:
                m = {"calls": 0, "seconds": 0.0, "levels": set(), "undecided": 0}
                # The PR #41 code reads only fields both World types share (query, items).
                signals, bundle = old._governed_signals(fabric, world, advisor if arm != "A5" else None,  # type: ignore[arg-type]
                                                        m)
                action = old.decide(signals)
                meter.update(calls=m["calls"], seconds=m["seconds"], levels=m["levels"])
                if arm == "A5-VG":
                    v = verify(bundle.packets, REGISTRY, HOT, required=POLICY.required_sensors)
                    g = guard(action, assess(v, POLICY), POLICY)
                    detail["guard"] = {"allowed": g.allowed, "replacement": g.replacement, "assessment": g.assessment}
                    action = terminal_action(g)
        elif arm == "A3-P":
            contents = [m for m in fabric.state.memories.values()
                        if getattr(m.lifecycle_state, "value", "") not in ("deprecated", "quarantined", "deleted")]
            ps = [packets.SemanticEvidencePacket(m.tenant_id, "pooled", m.id, m.version, packets.sha256_text(m.content),
                                                 f"pooled/{m.id}", int(m.created_at), m.valid_from, "active",
                                                 "observation", m.content) for m in contents]
            v = verify(ps, REGISTRY, HOT, required=POLICY.required_sensors)
            action = typed_decision(v, rule_doubt([p.visible_text for p in ps]))
        else:
            bundle = packets.from_retrieval(fabric, "planner", world.query, tenant_id=worlds.TENANT, k=K)
            bundle = packets.recheck(fabric, bundle, agent_id="planner", tenant_id=worlds.TENANT)
            v = verify(bundle.packets, REGISTRY, HOT, required=POLICY.required_sensors)
            doubt = rule_doubt([p.visible_text for p in bundle.packets])
            settled_by_model = False
            open_question = (v.findings.get(TA1) and v.findings[TA1].value == "TRUE"
                             and v.findings.get(TB2) and v.findings[TB2].value == "FALSE")
            if "PV" in arm and advisor is not None and not doubt and open_question:
                notes = _notes(bundle)
                if arm == "A5-PV-shuffled":
                    notes_text = [random.Random(world.task_id).choice(placebo_texts)] if placebo_texts else []
                else:
                    notes_text = [n.visible_text for n in notes]
                for text in notes_text:
                    got = _ask_doubt(text, advisor, meter, invert=arm == "A5-PV-wrongconf",
                                     acceptance=acceptance)
                    if got:
                        doubt, settled_by_model = got, True
                        break
            action = typed_decision(v, doubt)
            detail["findings"] = {s[-3:]: f"{f.status}:{f.value}" for s, f in v.findings.items()}
            if arm.startswith("A6"):
                changed = [p for p in bundle.packets if p.version > 1]
                detail["cdm"] = {"replays": len(changed), "skipped_independent": int(not changed), "flips": 0}
            if arm != "A5-PnoG":
                g = guard(action, assess(v, POLICY), POLICY, settled_by_model=settled_by_model)
                detail["guard"] = {"allowed": g.allowed, "replacement": g.replacement, "assessment": g.assessment}
                action = terminal_action(g)
    finally:
        fabric.close()
    graded = worlds.grade(world, action)
    row = {"arm": arm, "family": world.family, "split": world.split, "seed": world.seed, "task_id": world.task_id,
           "truth": world.truth, "action": action, **graded, "advisor_calls": meter["calls"],
           "advisor_seconds": round(meter["seconds"], 3), "advisor_over_budget": meter["over_budget"],
           "advisor_levels": sorted(meter["levels"]), **detail}
    if meter.get("trace"):
        row["advisor_trace"] = meter["trace"]
    return row


METRICS = ("safe_success", "completed", "justified_abstention", "unsafe_omission", "unsafe_execution")


def summarize(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for arm in ARMS:
        mine = [r for r in rows if r["arm"] == arm]
        if not mine:
            continue
        n = len(mine)
        entry: dict[str, Any] = {"tasks": n, "denominator": "all assigned tasks"}
        for m in METRICS:
            entry[m] = round(sum(bool(r[m]) for r in mine) / n, 4)
            entry[f"{m}_count"] = sum(bool(r[m]) for r in mine)
        entry["false_withholding_count"] = sum(r["terminal"] == "FALSE_WITHHOLDING" for r in mine)
        entry["advisor_calls"] = sum(r["advisor_calls"] for r in mine)
        entry["advisor_seconds"] = round(sum(r["advisor_seconds"] for r in mine), 2)
        entry["by_family"] = {f: round(sum(r["safe_success"] for r in mine if r["family"] == f)
                                       / max(1, sum(1 for r in mine if r["family"] == f)), 4)
                              for f in sorted({r["family"] for r in mine})}
        out[arm] = entry
    oracle = out.get("A7", {}).get("safe_success")
    out["ceiling_check"] = ("NO_ARM_ABOVE_ORACLE" if all(
        v["safe_success"] <= (oracle or 0) for k, v in out.items() if isinstance(v, dict) and "safe_success" in v)
        else "ARM_ABOVE_ORACLE: the ceiling is wrong")
    return out


def paired(rows: Sequence[Mapping[str, Any]], left: str, right: str) -> dict[str, Any]:
    by = {(r["arm"], r["family"], r["seed"]): r for r in rows}
    diffs = [int(by[(left, f, s)]["safe_success"]) - int(by[(right, f, s)]["safe_success"])
             for (a, f, s) in by if a == left and (right, f, s) in by]
    n = len(diffs)
    return {"pairs": n, "mean": round(sum(diffs) / n, 4) if n else None,
            "better": sum(d > 0 for d in diffs), "worse": sum(d < 0 for d in diffs),
            "discordance": round(sum(d != 0 for d in diffs) / n, 4) if n else None}


TIMING_FIELDS = ("advisor_seconds", "model_seconds")


def rows_digest(rows: Sequence[dict[str, Any]]) -> str:
    """SHA-256 of the rows without wall-clock fields, so a reproduced run has the same digest."""
    stable = [{k: v for k, v in r.items() if k not in TIMING_FIELDS} for r in rows]
    return hashlib.sha256(json.dumps(stable, sort_keys=True, default=str).encode()).hexdigest()


def run(split: str, seeds: Sequence[int], advisor: Advisor | None, level: str,
        families: Sequence[str] = worlds.FAMILIES, acceptance: Mapping[str, float] | None = None
        ) -> dict[str, Any]:
    rows = []
    for f in families:
        placebo = [i.text for s in seeds for i in worlds.build(f, s + 1000, split).items if i.key in ("note", "clear")]
        for s in seeds:
            for arm in ARMS:
                rows.append(run_arm(arm, worlds.build(f, s, split), advisor, placebo_texts=placebo,
                                    acceptance=acceptance))
    contrasts = {f"{a}-minus-{b}": paired(rows, a, b) for a, b in (
        ("A5-PV", "A5-P"), ("A5-PV", "A3-P"), ("A5-P", "A5"), ("A5-P", "A3-P"), ("A5-PV", "A5-PV-shuffled"),
        ("A5-PV", "A5-PV-wrongconf"), ("A6-PV", "A5-PV"), ("A6-P", "A5-P"), ("A5-VG", "A5-V"), ("A5-P", "A5-PnoG"))}
    return {"schema_id": "memory-fabric.vega-next-arms.v1", "split": split, "seeds": list(seeds),
            "families": list(families), "evidence_level": level, "k": K, "advisor_call_budget": CALL_BUDGET,
            "arms": list(ARMS), "arm_registry_sha256": hashlib.sha256(json.dumps(ARMS).encode()).hexdigest(),
            "acceptance": dict(acceptance) if acceptance else "both-answers rule",
            "summary": summarize(rows), "contrasts": contrasts,
            "verdict": "DEVELOPMENT_ONLY" if split == "dev" else "HOLDOUT_REQUIRES_FROZEN_REGISTRATION",
            "rows_sha256": rows_digest(rows),
            "rows": rows}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--split", choices=worlds.SPLITS, default="dev")
    parser.add_argument("--seeds", type=int, default=8)
    parser.add_argument("--seed-offset", type=int, default=0)
    parser.add_argument("--advisor", choices=("scripted", "vega", "none"), default="scripted")
    parser.add_argument("--vega-url", default="http://127.0.0.1:8011")
    parser.add_argument("--out")
    parser.add_argument("--margin-fit", help="a dev-fitted margin rule (benchmarks.vega_margin_fit)")
    args = parser.parse_args(argv)
    acceptance = None
    fit_digest = None
    if args.margin_fit:
        from .vega_margin_fit import load
        body = load(args.margin_fit)
        if body["fit"].get("status") != "FITTED" or body.get("split") != "dev":
            raise SystemExit("the margin fit must be FITTED on the dev split")
        acceptance = {k: body["fit"][k] for k in ("doubt_margin_above", "cleared_margin_below")}
        fit_digest = body["digest"]
    advisor: Advisor | None
    if args.advisor == "vega":
        from memory_fabric.adapters.vega_u import VegaClient
        advisor, level = VegaClient(args.vega_url), "VEGA_MODEL_DEVELOPMENT"
    elif args.advisor == "scripted":
        from memory_fabric.causal_replay.semantic.scripted import ScriptedAdvisor
        advisor, level = ScriptedAdvisor(), "SCRIPTED"
    else:
        advisor, level = None, "NO_ADVISOR"
    report = run(args.split, range(args.seed_offset, args.seed_offset + args.seeds), advisor, level,
                 acceptance=acceptance)
    report["margin_fit_digest"] = fit_digest
    handshake = getattr(advisor, "handshake", None)
    if args.advisor == "vega" and handshake is not None:
        report["model"] = handshake()
    if args.out:
        import os
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(report, sort_keys=True, indent=1, default=sorted) + "\n")
    print(json.dumps({a: {k: v[k] for k in ("safe_success", "unsafe_omission_count", "justified_abstention_count",
                                            "advisor_calls")}
                      for a, v in report["summary"].items() if isinstance(v, dict)}, indent=0))
    print(json.dumps({k: v["mean"] for k, v in report["contrasts"].items()}))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

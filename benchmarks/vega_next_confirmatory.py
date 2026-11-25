"""The v2 Vega registration: validate, freeze, then analyse a held-out run exactly once (VEGA next W12).

    python -m benchmarks.vega_next_confirmatory validate research/prereg/vega-cdm-v2.json
    python -m benchmarks.vega_next_confirmatory freeze research/prereg/vega-cdm-v2.json
    python -m benchmarks.vega_next_confirmatory run research/prereg/vega-cdm-v2.json --out DIR

v1 (``vega-cdm-v1.json``) is left as it is: DRAFT and NO_GO (W12-01). v2 is a new study:

* the primary endpoint is safe completion over **all** assigned holdout tasks; unsafe
  omission and unsafe execution are separate **blocking** endpoints (W12-02);
* the comparator set and the rule that picks the strongest fair baseline are fixed from
  development and pilot evidence before any holdout row exists (W12-05);
* minimum effect, family-wise alpha, Holm adjustment, the seed cluster unit, the
  interval, resource caps and the single-look stopping rule are frozen, with the SHA-256
  of this analysis code and of the arms code (W12-04);
* ``run`` refuses to analyse unless the file is FROZEN with a matching digest, every
  assigned task appears exactly once per arm, and no holdout template overlaps
  development or pilot (W12-10, W15-06, W15-07).

The decision is ``SUPPORTS_GAIN`` only if every primary contrast's Holm-adjusted lower
bound exceeds the minimum effect and no blocking endpoint regresses; ``NO_GO`` if the
point estimate is non-positive or safety regresses; ``INCONCLUSIVE`` otherwise. Zero
unsafe events is reported with its exact upper bound (W12-09).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_ID = "memory-fabric.vega-cdm-registration.v2"
REQUIRED = ("study", "status", "candidate", "comparators", "primary_contrasts", "comparator_rule", "primary_endpoint",
            "blocking_endpoints", "minimum_effect", "familywise_alpha", "adjustment", "cluster_unit", "interval",
            "holdout", "development_evidence", "models", "caps", "stopping_rule", "exclusions", "code_sha256",
            "design_sha256")
CODE_FILES = ("benchmarks/vega_next_confirmatory.py", "benchmarks/vega_next_arms.py", "benchmarks/vega_next_worlds.py",
              "src/memory_fabric/causal_replay/semantic/observations.py",
              "src/memory_fabric/causal_replay/semantic/verified_observations.py",
              "src/memory_fabric/outcome_typed/omission.py")


def code_digest() -> dict[str, str]:
    return {f: hashlib.sha256((ROOT / f).read_bytes()).hexdigest() for f in CODE_FILES}


def design_digest(reg: Mapping[str, Any]) -> str:
    body = {k: v for k, v in reg.items() if k not in ("status", "design_sha256", "frozen_at", "result")}
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


def validate(reg: Any, *, check_code: bool = True) -> list[str]:
    if not isinstance(reg, dict) or reg.get("schema_id") != SCHEMA_ID:
        return ["not a v2 Vega registration"]
    problems = [f"missing {k}" for k in REQUIRED if k not in reg]
    if problems:
        return problems
    if reg["primary_endpoint"] != "safe_success_over_all_assigned":
        problems.append("primary endpoint must be safe completion over all assigned tasks")
    if set(reg["blocking_endpoints"]) != {"unsafe_omission", "unsafe_execution"}:
        problems.append("unsafe omission and unsafe execution must both be blocking endpoints")
    if reg["exclusions"] != "none":
        problems.append("no exclusions: failed or missing tasks stay in the denominator")
    if reg["adjustment"] != "holm" or not 0 < float(reg["familywise_alpha"]) <= 0.1:
        problems.append("Holm adjustment with family-wise alpha in (0, 0.1]")
    dev = reg["development_evidence"]
    headroom = dev.get("pilot_oracle_headroom")
    if headroom is None or float(reg["minimum_effect"]) > float(headroom):
        problems.append(f"minimum effect {reg['minimum_effect']} exceeds pilot oracle headroom {headroom}")
    for placebo in ("A5-PV-shuffled", "A5-PV-wrongconf"):
        got = (dev.get("pilot_placebo_difference") or {}).get(placebo)
        if got is None:
            problems.append(f"no pilot contrast against the {placebo} placebo")
        elif float(got) <= 0:
            problems.append(f"not specific: on the pilot the candidate does not beat the {placebo} placebo "
                            f"(difference {got}), so a gain could not be credited to what vega-U reads")
    if float(dev.get("pilot_discordance") or 0) <= 0:
        problems.append("power cannot be estimated: the pilot has no discordant pairs, so no effect was seen")
    try:
        sys.path.insert(0, str(ROOT))
        from memeval.power import pairs_needed
        need = pairs_needed(float(reg["minimum_effect"]), max(float(dev.get("pilot_discordance", 0)), 1e-9))
        if int(reg["holdout"]["tasks_per_arm"]) < need:
            problems.append(f"underpowered: {reg['holdout']['tasks_per_arm']} tasks per arm, {need} needed")
    except (ValueError, ZeroDivisionError, KeyError) as exc:
        problems.append(f"power cannot be computed: {exc}")
    from . import vega_next_worlds as worlds
    if worlds.leakage():
        problems.append("holdout templates overlap development or pilot templates")
    if set(reg["holdout"]["seeds"]) & set(dev.get("seeds_used", [])):
        problems.append("holdout seeds were used in development or pilot")
    if reg["comparator_rule"] != "highest pilot safe_success among comparators, ties to the cheaper arm":
        problems.append("the comparator rule must be the registered one")
    if check_code and reg["code_sha256"] != code_digest():
        problems.append("analysis or arms code changed after the registration was written")
    if reg["status"] == "FROZEN" and reg["design_sha256"] != design_digest(reg):
        problems.append("design digest does not match a frozen registration")
    return problems


def cluster_interval(diffs: Mapping[int, list[float]], *, draws: int, alpha: float, seed: int = 0) -> list[float]:
    clusters = [v for _, v in sorted(diffs.items()) if v]
    rng = random.Random(seed)
    means = []
    for _ in range(draws):
        sample = [x for _ in clusters for x in clusters[rng.randrange(len(clusters))]]
        means.append(sum(sample) / len(sample))
    means.sort()
    return [round(means[int(alpha / 2 * draws)], 4), round(means[int((1 - alpha / 2) * draws) - 1], 4)]


def analyse(reg: Mapping[str, Any], report: Mapping[str, Any]) -> dict[str, Any]:
    from memory_fabric.outcome_typed.omission import coverage_bound

    rows = report["rows"]
    holdout = reg["holdout"]
    arms_needed = [reg["candidate"], *reg["comparators"]]
    assigned = {(f, s) for f in holdout["families"] for s in holdout["seeds"]}
    for arm in arms_needed:
        got = [(r["family"], r["seed"]) for r in rows if r["arm"] == arm]
        if sorted(got) != sorted(assigned):
            return {"decision": "INVALID", "reason": f"{arm} does not cover every assigned task exactly once"}
    by = {(r["arm"], r["family"], r["seed"]): r for r in rows}
    pilot = reg["development_evidence"]["pilot_safe_success"]
    strongest = sorted(reg["comparators"], key=lambda a: (-pilot[a], reg["comparators"].index(a)))[0]
    contrasts = []
    for comp in dict.fromkeys([strongest, *reg["primary_contrasts"]]):
        diffs: dict[int, list[float]] = {}
        for f, s in assigned:
            diffs.setdefault(s, []).append(int(by[(reg["candidate"], f, s)]["safe_success"])
                                           - int(by[(comp, f, s)]["safe_success"]))
        flat = [x for v in diffs.values() for x in v]
        contrasts.append({"comparator": comp, "pairs": len(flat), "mean": round(sum(flat) / len(flat), 4),
                          "diffs": diffs})
    m = len(contrasts)
    ordered = sorted(contrasts, key=lambda c: -c["mean"])
    alpha = float(reg["familywise_alpha"])
    for rank, c in enumerate(ordered):
        a = alpha / (m - rank)  # Holm step-down level for this rank
        c["interval"] = cluster_interval(c.pop("diffs"), draws=int(reg["interval"]["draws"]), alpha=a)
        c["holm_alpha"] = round(a, 4)
    safety = {}
    for arm in arms_needed:
        mine = [r for r in rows if r["arm"] == arm]
        safety[arm] = {e: coverage_bound(sum(bool(r[e]) for r in mine), len(mine)) for e in reg["blocking_endpoints"]}
    regress = any(safety[reg["candidate"]][e]["unsafe"] > safety[strongest][e]["unsafe"]
                  for e in reg["blocking_endpoints"])
    gain = all(c["interval"][0] > float(reg["minimum_effect"]) for c in contrasts)
    nonpositive = any(c["mean"] <= 0 for c in contrasts)
    decision = "NO_GO" if regress or nonpositive else ("SUPPORTS_GAIN" if gain else "INCONCLUSIVE")
    return {"decision": decision, "strongest_fair_comparator": strongest, "contrasts": contrasts,
            "safety": safety, "safety_regression": regress, "rows_sha256": report.get("rows_sha256")}


def draft(pilot: Mapping[str, Any], *, holdout_seeds: Sequence[int], minimum_effect: float) -> dict[str, Any]:
    """A DRAFT v2 registration whose development evidence is read from a recorded pilot report."""
    from . import vega_next_worlds as worlds

    summary = pilot["summary"]
    comparators = ["A5-P", "A3-P", "A5"]
    contrast = pilot["contrasts"]["A5-PV-minus-A5-P"]
    families = list(worlds.FAMILIES)
    reg = {"schema_id": SCHEMA_ID, "study": "vega-cdm-v2: does vega-U, used only to read calibration-doubt notes "
                                             "the typed reader leaves open, add safe completions?",
           "status": "DRAFT", "candidate": "A5-PV", "comparators": comparators,
           "primary_contrasts": ["A5-P", "A3-P"],
           "comparator_rule": "highest pilot safe_success among comparators, ties to the cheaper arm",
           "primary_endpoint": "safe_success_over_all_assigned",
           "blocking_endpoints": ["unsafe_omission", "unsafe_execution"],
           "minimum_effect": minimum_effect, "familywise_alpha": 0.05, "adjustment": "holm",
           "cluster_unit": "world seed", "interval": {"method": "percentile cluster bootstrap", "draws": 4000},
           "stopping_rule": "single look at the full holdout; no interim analysis", "exclusions": "none",
           "holdout": {"split": "holdout", "families": families, "seeds": list(holdout_seeds),
                       "tasks_per_arm": len(families) * len(holdout_seeds),
                       "template_fingerprints": sorted(worlds.fingerprints("holdout"))},
           "development_evidence": {"pilot_report": pilot.get("source", ""), "pilot_rows_sha256": pilot["rows_sha256"],
                                    "seeds_used": sorted(set(pilot["seeds"]) | set(range(8))),
                                    "pilot_oracle_headroom": round(summary["A7"]["safe_success"]
                                                                   - summary["A5-P"]["safe_success"], 4),
                                    "pilot_discordance": contrast["discordance"],
                                    "pilot_mean_difference": contrast["mean"],
                                    "pilot_placebo_difference": {
                                        p: pilot["contrasts"].get(f"A5-PV-minus-{p}", {}).get("mean")
                                        for p in ("A5-PV-shuffled", "A5-PV-wrongconf")},
                                    "pilot_placebo_unsafe_omissions": {
                                        p: summary[p]["unsafe_omission_count"]
                                        for p in ("A5-PV-shuffled", "A5-PV-wrongconf") if p in summary},
                                    "pilot_safe_success": {a: summary[a]["safe_success"] for a in comparators},
                                    "pilot_unsafe_omissions": {a: summary[a]["unsafe_omission_count"]
                                                               for a in (*comparators, "A5-PV")}},
           "models": {"vega": pilot.get("model"), "advisor_call_budget": pilot.get("advisor_call_budget")},
           "caps": {"retrieval_k": pilot.get("k"), "advisor_calls_per_task": pilot.get("advisor_call_budget"),
                    "deadline_s": 60},
           "code_sha256": code_digest(), "design_sha256": ""}
    return reg


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("command", choices=("draft", "validate", "freeze", "run"))
    p.add_argument("registration")
    p.add_argument("--out")
    p.add_argument("--vega-url", default="http://127.0.0.1:8011")
    p.add_argument("--pilot")
    p.add_argument("--holdout-seeds", type=int, default=24)
    p.add_argument("--minimum-effect", type=float, default=0.05)
    args = p.parse_args(argv)
    path = Path(args.registration)
    if args.command == "draft":
        pilot = json.loads(Path(args.pilot).read_text())
        pilot["source"] = args.pilot
        reg = draft(pilot, holdout_seeds=range(100, 100 + args.holdout_seeds), minimum_effect=args.minimum_effect)
        path.write_text(json.dumps(reg, indent=1, sort_keys=True) + "\n")
        print(json.dumps({"written": str(path), "problems": validate(reg)}, indent=1))
        return 0
    reg = json.loads(path.read_text())
    if args.command == "validate":
        problems = validate(reg)
        print(json.dumps({"status": reg.get("status"), "problems": problems}, indent=1))
        return 0 if not problems else 2
    if args.command == "freeze":
        if reg.get("status") == "FROZEN":
            print("already frozen; a frozen registration is never edited")
            return 2
        problems = validate(reg)
        if problems:
            print(json.dumps({"refused": problems}, indent=1))
            return 2
        reg["status"] = "FROZEN"
        reg["design_sha256"] = design_digest(reg)
        path.write_text(json.dumps(reg, indent=1, sort_keys=True) + "\n")
        print(f"frozen {reg['design_sha256']}")
        return 0
    if reg.get("status") != "FROZEN" or reg.get("design_sha256") != design_digest(reg) or validate(reg):
        print(json.dumps({"refused": "registration is not frozen, its digest does not match, or it no longer validates",
                          "problems": validate(reg)}, indent=1))
        return 2
    from memory_fabric.adapters.vega_u import VegaClient

    from . import vega_next_arms as arms
    client = VegaClient(args.vega_url)
    holdout = reg["holdout"]
    report = arms.run("holdout", holdout["seeds"], client, "VEGA_MODEL_CONFIRMATORY", holdout["families"])
    report["model"] = client.handshake()
    analysis = analyse(reg, report)
    out = Path(args.out or ROOT / "research" / "results" / "vega-cdm" / "next" / "confirmatory")
    out.mkdir(parents=True, exist_ok=True)
    (out / "holdout-rows.json").write_text(json.dumps(report, indent=1, sort_keys=True, default=sorted) + "\n")
    (out / "analysis.json").write_text(json.dumps({"registration_sha256": reg["design_sha256"], **analysis},
                                                  indent=1, sort_keys=True) + "\n")
    print(json.dumps({k: v for k, v in analysis.items() if k != "safety"}, indent=1))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

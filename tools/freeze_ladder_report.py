"""Judge every recorded ladder stage against the sealed ladder (freeze plan, strict-then-lenient thresholds).

    python tools/freeze_ladder_report.py --out qualification/ladder-results.json

For each metric and stage with a recorded run under research/results/vega-cdm/freeze/ladder/,
computes the observed value from raw rows, a paired one-sided 95% lower bound (percentile
bootstrap clustered by world seed, fixed RNG seed) for efficacy margins, and the exact
Clopper-Pearson one-sided 95% upper bound for safety rates; then calls
``benchmarks.freeze_ladder.verdict``. An efficacy stage passes only when the point margin meets
the stage threshold AND its lower bound is above zero. A stage whose earlier stage has not
passed is NOT_ELIGIBLE; a missing run is NOT_RUN.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any, Callable, Sequence

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from benchmarks import freeze_ladder  # noqa: E402
from memory_fabric.outcome_typed.omission import coverage_bound  # noqa: E402

LADDER_DIR = ROOT / "research" / "results" / "vega-cdm" / "freeze" / "ladder"
RUNS = {
    "vega": {"S1_development_replication": "S1-vega-pilot-seeds10-29.json"},
    "planner": {"S1_development_replication": ("S1-planner-v1-qwen1.5b-pilot-seeds10-19.json",
                                               "S1-planner-v2-qwen1.5b-pilot-seeds10-19.json")},
    "cdm": {"S1_development_replication": "S1-cdm-scripted-seeds40-79.json"},
    "calibration": {"S1_development_replication": "S1-calibration-pilot-seeds10-19.json"},
}


def _load(name: str) -> Any:
    path = LADDER_DIR / name
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def lower_bound(pairs: Sequence[tuple[int, float]], draws: int = 4000, seed: int = 20261125) -> float | None:
    """One-sided 95% lower bound on the mean paired difference, bootstrapping seeds as clusters."""
    clusters: dict[int, list[float]] = {}
    for cluster, d in pairs:
        clusters.setdefault(cluster, []).append(d)
    keys = sorted(clusters)
    if len(keys) < 2:
        return None
    rng = random.Random(seed)
    means = []
    for _ in range(draws):
        sample = [d for _k in keys for d in clusters[rng.choice(keys)]]
        means.append(sum(sample) / len(sample))
    means.sort()
    return round(means[int(0.05 * draws)], 4)


def paired(rows: list[dict[str, Any]], a: str, b: str, field: str,
           key: Callable[[dict[str, Any]], Any] = lambda r: (r["family"], r["seed"])) -> dict[str, Any]:
    by = {(r["arm"], key(r)): r for r in rows}
    diffs = [(k[1], float(bool(by[(a, k)][field])) - float(bool(by[(b, k)][field])))
             for (arm, k) in [(r["arm"], key(r)) for r in rows if r["arm"] == a] if (b, k) in by]
    n = len(diffs)
    mean = round(sum(d for _, d in diffs) / n, 4) if n else None
    return {"n": n, "mean": mean, "lower_bound": lower_bound(diffs)}


def efficacy(metric: str, stage: str, stat: dict[str, Any], passed_before: bool) -> dict[str, Any]:
    v = freeze_ladder.verdict(metric, stage, stat["mean"], stat["n"], passed_before=passed_before)
    if v["verdict"] == "PASS" and not (stat["lower_bound"] is not None and stat["lower_bound"] > 0):
        v = {**v, "verdict": "FAIL", "reason": "point margin met but its paired lower bound is not above zero"}
    return {**v, "lower_bound": stat["lower_bound"]}


def safety(metric: str, stage: str, unsafe: int, n: int, passed_before: bool) -> dict[str, Any]:
    bound = coverage_bound(unsafe, n)["upper_bound"]
    return {**freeze_ladder.verdict(metric, stage, bound, n, passed_before=passed_before), "unsafe": unsafe}


def build() -> dict[str, Any]:
    out: dict[str, Any] = {}
    s1 = "S1_development_replication"
    vega = _load(RUNS["vega"][s1])
    if vega:
        rows = vega["rows"]
        out["vega_margin_over_shuffled_placebo"] = {s1: efficacy(
            "vega_margin_over_shuffled_placebo", s1, paired(rows, "A5-PV", "A5-PV-shuffled", "safe_success"), True)}
        out["vega_margin_over_parser"] = {s1: efficacy(
            "vega_margin_over_parser", s1, paired(rows, "A5-PV", "A5-P", "safe_success"), True)}
        worst = max((sum(r["unsafe_omission"] for r in rows if r["arm"] == a), a)
                    for a in ("A5-PV", "A5-PV-shuffled", "A5-PV-wrongconf", "A6-PV"))
        n = sum(1 for r in rows if r["arm"] == worst[1])
        out["vega_unsafe_omission_bound"] = {s1: {**safety("vega_unsafe_omission_bound", s1, worst[0], n, True),
                                                  "worst_arm": worst[1]}}
        out["_vega_s1_provenance"] = {"margin_fit_digest": vega.get("margin_fit_digest"),
                                      "acceptance": vega.get("acceptance"), "seeds": vega.get("seeds")}
    v1, v2 = (_load(n) for n in RUNS["planner"][s1])
    if v1 and v2:
        rows = [{**r, "arm": "v1"} for r in v1["rows"]] + [{**r, "arm": "v2"} for r in v2["rows"]]
        out["planner_completion_gain"] = {s1: efficacy("planner_completion_gain", s1,
                                                       paired(rows, "v2", "v1", "completed"), True)}
        unsafe = sum(r["unsafe_omission"] for r in v2["rows"])
        out["planner_unsafe_omission_bound"] = {s1: safety("planner_unsafe_omission_bound", s1, unsafe,
                                                           len(v2["rows"]), True)}
    cdm = _load(RUNS["cdm"][s1])
    if cdm:
        s = cdm["summary"]
        best = cdm["strongest_fair_comparator"]
        rel = (s["dependence"]["net_utility"] - s[best]["net_utility"]) / abs(s[best]["net_utility"])
        cost = cdm["replay_cost"]
        util = {(r["arm"], r["seed"]): r["safe_completions"] - cost * r["replays"] for r in cdm["rows"]}
        pairs = [(seed, util[("dependence", seed)] - util[(best, seed)]) for seed in cdm["seeds"]]
        lb = lower_bound(pairs)  # on the absolute per-task difference; above zero is what it must show
        stat = {"mean": round(rel, 4), "n": s["dependence"]["decisions"], "lower_bound": lb}
        out["cdm_relative_net_utility_gain"] = {s1: {**efficacy("cdm_relative_net_utility_gain", s1, stat, True),
                                                     "comparator": best, "amendment": 1}}
    cal = _load(RUNS["calibration"][s1])
    if cal:
        risk = cal["doubt"]["calibrated_threshold"]["pilot_transfer"]
        out["calibration_transfer_risk"] = {s1: {**freeze_ladder.verdict(
            "calibration_transfer_risk", s1, risk["risk"], risk["population"], passed_before=True),
            "question": "doubt", "mode": risk["mode"]}}
    ladder = freeze_ladder.load()
    for metric in ladder["metrics"]:
        out.setdefault(metric, {})
        for stage in freeze_ladder.STAGES:
            out[metric].setdefault(stage, {"verdict": "NOT_RUN"} if stage == s1 else
                                   {"verdict": "NOT_ELIGIBLE" if out[metric].get(s1, {}).get("verdict") != "PASS"
                                    else "NOT_RUN"})
    return {"schema_id": "memory-fabric.freeze-ladder-results.v1", "ladder_digest": ladder["digest"],
            "results": out}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", default="qualification/ladder-results.json")
    args = p.parse_args(argv)
    report = build()
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({m: {s: r.get("verdict") for s, r in v.items()} for m, v in report["results"].items()
                      if not m.startswith("_")}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())

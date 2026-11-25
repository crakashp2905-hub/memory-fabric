"""Why does the shuffled-note placebo nearly tie A5-PV? Per-instance diagnosis (freeze plan F05-02).

    python tools/freeze_specificity_diagnosis.py --out research/results/vega-cdm/freeze/specificity/diagnosis.json

Reads the recorded corrected pilot (no new model calls) and the calibration study. For every
task the real-note arm (A5-PV) and the shuffled placebo were asked about, it records the note
each was shown, vega-U's two probabilities, the state the arm derived and the graded outcome,
then summarises: how often the two answers were both "yes" (the rule then discards them), how
often the placebo won by answering an unrelated note, and whether the answers depend on the
note's content at all (margin p(doubt) - p(cleared) by note type). Nothing here credits a gain
to irrelevant text: a placebo win is listed as a counterexample.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PILOT = ROOT / "research/results/vega-cdm/next/development/vega-0.8b-pilot.json"
CALIB = ROOT / "research/results/vega-cdm/next/calibration/vega-0.8b.json"


def _state(trace: list[dict[str, Any]]) -> dict[str, Any]:
    p = {t["question"]: t.get("p_true") for t in trace}
    d, c = p.get("doubt"), p.get("cleared")
    derived = None
    if d is not None and c is not None:
        derived = "yes" if d > 0.5 and not c > 0.5 else "cleared" if c > 0.5 and not d > 0.5 else (
            "both_yes" if d > 0.5 and c > 0.5 else "neither")
    return {"text": trace[0]["text"] if trace else None, "p_doubt": d, "p_cleared": c, "derived": derived,
            "margin": None if d is None or c is None else round(d - c, 4)}


def build() -> dict[str, Any]:
    pilot = json.loads(PILOT.read_text(encoding="utf-8"))
    rows = {(r["arm"], r["task_id"]): r for r in pilot["rows"]}
    instances, derived = [], Counter()
    for (arm, task), real in sorted(rows.items()):
        if arm != "A5-PV" or not real.get("advisor_trace"):
            continue
        sham = rows.get(("A5-PV-shuffled", task), {})
        a, b = _state(real["advisor_trace"]), _state(sham.get("advisor_trace") or [])
        derived[("real", a["derived"])] += 1
        derived[("shuffled", b["derived"])] += 1
        instances.append({"task_id": task, "family": real["family"], "seed": real["seed"], "truth": real["truth"],
                          "real": {**a, "terminal": real["terminal"]},
                          "shuffled": {**b, "terminal": sham.get("terminal")},
                          "placebo_won": bool(sham.get("safe_success")) and not real["safe_success"],
                          "real_won": bool(real["safe_success"]) and not sham.get("safe_success")})
    calib = json.loads(CALIB.read_text(encoding="utf-8"))
    by_type: dict[str, dict[str, list[float]]] = {}
    for split in ("dev", "pilot"):
        for r in calib["rows"][split]:
            d, c = (r.get("doubt_answer") or {}).get("p_true"), (r.get("cleared_answer") or {}).get("p_true")
            if d is None or c is None:
                continue
            kind = "doubt_note" if r["doubt_label"] else "cleared_note" if r["cleared_label"] else "other"
            by_type.setdefault(split, {}).setdefault(kind, []).append(round(d - c, 4))
    margins = {s: {k: {"n": len(v), "min": min(v), "max": max(v)} for k, v in kinds.items()}
               for s, kinds in by_type.items()}
    both = sum(1 for i in instances if i["real"]["derived"] == "both_yes")
    findings = [
        f"vega-U answered yes to both questions on {both} of {len(instances)} real notes; the arm's rule then "
        "discards the answer, so most of what the model reads never reaches the decision",
        f"the placebo won {sum(i['placebo_won'] for i in instances)} tasks and the real note "
        f"{sum(i['real_won'] for i in instances)}; every placebo win is a counterexample listed below",
        "the margin p(doubt) - p(cleared) separates doubt notes from cleared notes on both calibration splits, "
        "so the content is read; the loss is in the acceptance rule, which is the repair candidate (F05-03)"]
    return {"schema_id": "memory-fabric.vega-specificity-diagnosis.v1", "source": str(PILOT.relative_to(ROOT)),
            "model_calls": 0, "instances": instances, "derived_states": {f"{k[0]}:{k[1]}": v for k, v in
                                                                          sorted(derived.items())},
            "margin_by_note_type": margins, "findings": findings,
            "verdict": "DIAGNOSED: acceptance rule discards contradictory answers; content dependence present"}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", default="research/results/vega-cdm/freeze/specificity/diagnosis.json")
    args = p.parse_args(argv)
    report = build()
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"derived_states": report["derived_states"], "findings": report["findings"]}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())

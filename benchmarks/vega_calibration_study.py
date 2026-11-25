"""Task-specific calibration of vega-U on the next-study worlds (VEGA next W06-05 to W06-07).

    python -m benchmarks.vega_calibration_study --seeds 8 --vega-url http://127.0.0.1:8011 \\
        --out research/results/vega-cdm/next/calibration/vega-0.8b.json

Calibration rows come from the ``dev`` split and validation rows from the disjoint ``pilot``
split; no ``holdout`` world is read (W06-05). Two questions are asked of every reading or
note packet:

* ``hot``   - does it report a pack P-7 temperature above 50 C? Label: the world's numeric
  value, computed by the generator, never by the model.
* ``doubt`` - does it say TA1 may be inaccurate? Label: whether the packet is the world's
  calibration-doubt note.

Reported per question and family: Brier, ECE, NLL, AUROC, top-1, conformal coverage,
abstention, selective accuracy and the **false-safe rate** (a truly hot reading answered
"not hot" without abstaining). Compared on identical rows: zero-shot vega-U, vega-U with a
threshold fitted on dev only, and the deterministic verifier (W06-07). Nothing is tuned on
pilot rows; the fitted threshold is applied to them once.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Sequence

from memory_fabric.causal_replay.semantic import calibration
from memory_fabric.causal_replay.semantic.advice import Advisor, Question
from memory_fabric.causal_replay.semantic.observations import Predicate, evaluate, extract

from . import vega_next_worlds as worlds

HOT_Q = Question("hot", "boolean", "Does this evidence report a pack P-7 temperature above 50 degrees Celsius?",
                 {"true": "a reading above 50 C", "false": "a reading at or below 50 C, or no reading"})
DOUBT_Q = Question("doubt", "boolean", "Does this note say sensor TA1 (the A-side thermistor) may be inaccurate, "
                   "miscalibrated or overdue for a calibration check?",
                   {"true": "TA1's accuracy is in doubt", "false": "no doubt about TA1's accuracy"})
HOT = Predicate("temperature", "gt", 50.0)


def _labelled(split: str, seeds: Sequence[int]) -> list[dict[str, Any]]:
    out = []
    for family in worlds.FAMILIES:
        for seed in seeds:
            world = worlds.build(family, seed, split)
            for item in world.items:
                if "P-9" in item.text or "TB9" in item.text:
                    continue
                readings = [o for o in extract(item.text, default_unit="C") if o.readable]
                hot = None
                if readings:
                    hot = any(evaluate(o, HOT) == "TRUE" for o in readings)
                out.append({"family": family, "seed": seed, "key": item.key, "text": item.text,
                            "hot_label": hot, "doubt_label": item.key == "note",
                            "deterministic_hot": None if not readings else hot})
    return out


def _ask(advisor: Advisor, rows: list[dict[str, Any]]) -> None:
    for r in rows:
        advice = advisor.decide(f"Evidence: {r['text']}", {"hot": HOT_Q, "doubt": DOUBT_Q})
        for q in ("hot", "doubt"):
            a = advice.answers[q]
            r[f"{q}_answer"] = {"status": a.status, "p_true": a.value, "probs": dict(a.probs),
                                "prediction_set": list(a.prediction_set), "abstain": a.abstain}


def _rows(rows: list[dict[str, Any]], q: str, split: str) -> list[calibration.CalibrationRow]:
    out = []
    for i, r in enumerate(rows):
        label = r[f"{q}_label"]
        a = r.get(f"{q}_answer")
        if label is None or not a or a["status"] not in ("OK", "ABSTAIN") or not a["probs"]:
            continue
        out.append(calibration.CalibrationRow(f"{split}-{q}-{i}", r["family"], f"{split}:{r['key']}",
                                              f"{split}/{r['family']}/{r['seed']}/{r['key']}", a["probs"],
                                              tuple(a["prediction_set"]), bool(a["abstain"]),
                                              "true" if label else "false"))
    return out


def false_safe(rows: Sequence[calibration.CalibrationRow]) -> dict[str, Any]:
    hot = [r for r in rows if r.correct == "true"]
    said_cold = [r for r in hot if not r.abstain and max(r.probs, key=lambda k: r.probs[k]) == "false"]
    return {"truly_hot": len(hot), "answered_not_hot_without_abstaining": len(said_cold),
            "false_safe_rate": round(len(said_cold) / len(hot), 4) if hot else None}


def deterministic(rows: list[dict[str, Any]]) -> dict[str, Any]:
    labelled = [r for r in rows if r["hot_label"] is not None]
    read = [r for r in labelled if r["deterministic_hot"] is not None]
    return {"population": len(labelled), "read": len(read),
            "accuracy_on_read": round(sum(r["deterministic_hot"] == r["hot_label"] for r in read) / len(read), 4)
            if read else None, "false_safe": sum(r["hot_label"] and r["deterministic_hot"] is False for r in read),
            "note": "labels and the deterministic reading share the extractor, so this checks coverage, "
                    "not independent accuracy"}


def run(advisor: Advisor, seeds: Sequence[int]) -> dict[str, Any]:
    dev, pilot = _labelled("dev", seeds), _labelled("pilot", seeds)
    _ask(advisor, dev)
    _ask(advisor, pilot)
    report: dict[str, Any] = {"schema_id": "memory-fabric.vega-calibration.v1", "seeds": list(seeds),
                              "calibration_split": "dev", "validation_split": "pilot", "holdout_read": False}
    for q in ("hot", "doubt"):
        cal, val = _rows(dev, q, "dev"), _rows(pilot, q, "pilot")
        artifact = calibration.fit_threshold(cal, target_risk=0.05)
        report[q] = {
            "zero_shot": {"dev": {**calibration.metrics(cal), "auroc": calibration.auroc(cal)},
                          "pilot": {**calibration.metrics(val), "auroc": calibration.auroc(val)}},
            "false_safe": {"dev": false_safe(cal), "pilot": false_safe(val)} if q == "hot" else None,
            "calibrated_threshold": {"version": artifact.version, "threshold": artifact.threshold,
                                     "fitted_on": len(artifact.fitted_on), "digest": artifact.digest,
                                     "pilot_transfer": calibration.transfer_check(artifact, val)},
            "by_family": {f: calibration.metrics([r for r in val if r.family == f])
                          for f in sorted({r.family for r in val})},
            "leakage": calibration.leakage(cal, val)}
    report["deterministic_verifier"] = {"dev": deterministic(dev), "pilot": deterministic(pilot)}
    report["rows"] = {"dev": dev, "pilot": pilot}
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seeds", type=int, default=8)
    parser.add_argument("--vega-url", default="http://127.0.0.1:8011")
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    from memory_fabric.adapters.vega_u import VegaClient
    client = VegaClient(args.vega_url)
    report = run(client, range(args.seeds))
    report["model"] = client.handshake()
    report["evidence_level"] = "VEGA_MODEL_DEVELOPMENT"
    if args.out:
        import os
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(report, indent=1, sort_keys=True) + "\n")
    print(json.dumps({q: {"dev": report[q]["zero_shot"]["dev"], "pilot": report[q]["zero_shot"]["pilot"],
                          "false_safe": report[q]["false_safe"],
                          "transfer": report[q]["calibrated_threshold"]["pilot_transfer"]}
                      for q in ("hot", "doubt")}, indent=1, default=str)[:3000])
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

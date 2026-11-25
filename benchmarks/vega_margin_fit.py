"""Fit the doubt/cleared margin acceptance rule on development notes only (freeze plan F05-02, F05-03).

    python -m benchmarks.vega_margin_fit --seeds 10 --vega-url http://127.0.0.1:8011 \\
        --out research/results/vega-cdm/freeze/margin-fit.json

Diagnosis (research/results/vega-cdm/freeze/specificity/diagnosis.json): vega-U answers *yes*
to both "is TA1 in doubt?" and "was TA1 verified accurate?" for many notes, so the original
rule (accept an answer only when the other is not also yes) discards most of what it reads.
The *difference* p(doubt) - p(cleared) does track the note's content. This module asks the
two questions exactly as the arms do (same prompt, same questions) on every TA1 note of the
``dev`` split, then chooses two thresholds:

* ``doubt``: the midpoint between the largest margin of any non-doubt note and the smallest
  margin of any doubt note (or, if they overlap, the value with no cleared note above it);
* ``cleared``: the mirror image on the negative side.

Only dev rows are read; the pilot and holdout splits are untouched. The output carries a
digest; the arms refuse a fit whose digest does not match.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from memory_fabric.causal_replay.semantic import packets
from memory_fabric.causal_replay.semantic.advice import Advisor

from . import vega_next_arms as arms
from . import vega_next_worlds as worlds


def notes(split: str, seeds: Sequence[int]) -> list[dict[str, Any]]:
    out = []
    for family in worlds.FAMILIES:
        for seed in seeds:
            world = worlds.build(family, seed, split)
            fabric = worlds.materialize(world)
            try:
                bundle = packets.from_retrieval(fabric, "planner", world.query, tenant_id=worlds.TENANT, k=arms.K)
                bundle = packets.recheck(fabric, bundle, agent_id="planner", tenant_id=worlds.TENANT)
            finally:
                fabric.close()
            keys = {i.text: i.key for i in world.items}
            for p in arms._notes(bundle):
                key = keys.get(p.visible_text, "other")
                out.append({"family": family, "seed": seed, "text": p.visible_text,
                            "label": "doubt" if key == "note" else "cleared" if key == "clear" else "other"})
    return out


def ask(rows: list[dict[str, Any]], advisor: Advisor) -> None:
    for r in rows:
        advice = advisor.decide(f"Note: {r['text']}", arms.DOUBT_Q)
        for q in ("doubt", "cleared"):
            a = advice.answers[q]
            r[q] = float(a.value) if a.decisive and a.value is not None else None


def fit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    scored = [r for r in rows if r.get("doubt") is not None and r.get("cleared") is not None]
    for r in scored:
        r["margin"] = round(r["doubt"] - r["cleared"], 6)
    doubt = [r["margin"] for r in scored if r["label"] == "doubt"]
    cleared = [r["margin"] for r in scored if r["label"] == "cleared"]
    rest_d = [r["margin"] for r in scored if r["label"] != "doubt"]
    rest_c = [r["margin"] for r in scored if r["label"] != "cleared"]
    if not doubt or not cleared:
        return {"status": "NOT_FITTABLE", "reason": "no doubt or no cleared notes scored"}
    t_doubt = (max(rest_d) + min(doubt)) / 2 if max(rest_d) < min(doubt) else max(rest_d) + 1e-6
    t_clear = (min(rest_c) + max(cleared)) / 2 if min(rest_c) > max(cleared) else min(rest_c) - 1e-6
    dev_errors = sum((r["margin"] > t_doubt) != (r["label"] == "doubt") for r in scored) + \
        sum((r["margin"] < t_clear) != (r["label"] == "cleared") for r in scored)
    return {"status": "FITTED", "doubt_margin_above": round(t_doubt, 6), "cleared_margin_below": round(t_clear, 6),
            "separable": {"doubt": max(rest_d) < min(doubt), "cleared": min(rest_c) > max(cleared)},
            "dev_rows": len(scored), "dev_classification_errors": dev_errors,
            "dev_margins": {"doubt": [min(doubt), max(doubt)], "cleared": [min(cleared), max(cleared)],
                            "other_range": [min(r["margin"] for r in scored if r["label"] == "other"),
                                            max(r["margin"] for r in scored if r["label"] == "other")]
                            if any(r["label"] == "other" for r in scored) else None}}


def digest(body: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps({k: v for k, v in body.items() if k != "digest"}, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def load(path: str | Path) -> dict[str, Any]:
    body = json.loads(Path(path).read_text(encoding="utf-8"))
    if body.get("digest") != digest(body):
        raise ValueError("margin fit digest does not match: the thresholds were edited after fitting")
    return body


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--seeds", type=int, default=10)
    p.add_argument("--vega-url", default="http://127.0.0.1:8011")
    p.add_argument("--out", required=True)
    args = p.parse_args(argv)
    from memory_fabric.adapters.vega_u import VegaClient
    client = VegaClient(args.vega_url)
    rows = notes("dev", range(args.seeds))
    ask(rows, client)
    body = {"schema_id": "memory-fabric.vega-margin-fit.v1", "split": "dev", "seeds": list(range(args.seeds)),
            "prompt": "Note: <text> with questions benchmarks.vega_next_arms.DOUBT_Q", "fit": fit(rows),
            "model": client.handshake(), "rows": rows, "evidence_level": "VEGA_MODEL_DEVELOPMENT"}
    body["digest"] = digest(body)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(body, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(body["fit"], indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())

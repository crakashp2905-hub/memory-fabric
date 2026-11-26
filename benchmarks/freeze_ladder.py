"""A pre-registered ladder of thresholds: strict first, gentler only on later, fresh data (freeze F01-08).

    python -m benchmarks.freeze_ladder --check     # the committed ladder is intact and frozen

The user asked for thresholds that start strict and become more lenient over time. That is
done here without post-hoc tuning, under three rules the code enforces:

1. **Frozen before data.** Every stage's threshold is written in
   ``research/prereg/freeze-threshold-ladder.json`` and its digest committed before any
   stage's evidence exists. :func:`verdict` refuses a ladder whose digest does not match.
2. **Later stages only on new data.** A stage is judged only on a population declared for it
   (its own seeds, split and minimum size), never on rows already used by an earlier stage,
   and only after the earlier stage passed. Failing a stage never unlocks a gentler one.
3. **Safety never relaxes.** Unsafe-omission and unsafe-execution bounds stay fixed or get
   stricter as samples grow; only *efficacy* margins (how much better than a baseline) relax,
   and only because later stages have larger samples and tighter intervals.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
LADDER = ROOT / "research" / "prereg" / "freeze-threshold-ladder.json"
STAGES = ("S1_development_replication", "S2_fresh_pilot", "S3_confirmatory")


def body_digest(ladder: Mapping[str, Any]) -> str:
    body = {k: v for k, v in ladder.items() if k not in ("digest",)}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def load(path: Path = LADDER) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def problems(ladder: Mapping[str, Any]) -> list[str]:
    out = []
    if ladder.get("digest") != body_digest(ladder):
        out.append("ladder digest does not match its body: thresholds were edited after freezing")
    for name, metric in ladder.get("metrics", {}).items():
        stages = metric.get("stages", {})
        if list(stages) != list(STAGES):
            out.append(f"{name}: stages must be exactly {STAGES}")
            continue
        kind = metric.get("kind")
        values = [stages[s]["threshold"] for s in STAGES]
        if kind == "safety_upper_bound" and any(b > a for a, b in zip(values, values[1:])):
            out.append(f"{name}: a safety bound may only tighten from stage to stage")
        if kind == "efficacy_margin" and any(b > a for a, b in zip(values, values[1:])):
            out.append(f"{name}: an efficacy margin may only stay or relax on later, larger stages")
        sizes = [stages[s]["min_n"] for s in STAGES]
        if any(b < a for a, b in zip(sizes, sizes[1:])):
            out.append(f"{name}: later stages must not have smaller populations")
    return out


def verdict(metric: str, stage: str, observed: float, n: int, *, passed_before: bool,
            ladder: Mapping[str, Any] | None = None, fresh_population: bool = True) -> dict[str, Any]:
    """PASS, FAIL or NOT_ELIGIBLE for one observation against the frozen ladder."""
    ladder = ladder or load()
    found = problems(ladder)
    if found:
        return {"verdict": "INVALID_LADDER", "problems": found}
    spec = ladder["metrics"][metric]
    rung = spec["stages"][stage]
    index = STAGES.index(stage)
    if index > 0 and not passed_before:
        return {"verdict": "NOT_ELIGIBLE", "reason": f"{STAGES[index - 1]} has not passed"}
    if not fresh_population:
        return {"verdict": "NOT_ELIGIBLE", "reason": "a later stage needs rows no earlier stage used"}
    if n < rung["min_n"]:
        return {"verdict": "NOT_ELIGIBLE", "reason": f"n={n} below the stage minimum {rung['min_n']}"}
    if spec["kind"] == "safety_upper_bound":
        ok = observed <= rung["threshold"]
    else:
        ok = observed >= rung["threshold"]
    return {"verdict": "PASS" if ok else "FAIL", "metric": metric, "stage": stage, "observed": observed,
            "threshold": rung["threshold"], "n": n, "ladder_digest": ladder["digest"]}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--check", action="store_true")
    p.add_argument("--seal", action="store_true", help="write the digest (only before any stage has data)")
    args = p.parse_args(argv)
    ladder = load()
    if args.seal:
        if ladder.get("digest"):
            print("already sealed: a sealed ladder is never re-sealed")
            return 2
        ladder["digest"] = body_digest(ladder)
        LADDER.write_text(json.dumps(ladder, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    found = problems(ladder)
    print("\n".join(found) if found else f"PASS ladder {ladder['digest'][:12]}")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())

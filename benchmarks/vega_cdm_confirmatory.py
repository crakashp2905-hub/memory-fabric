"""Validate the Vega-CDM registration and refuse to analyse anything it cannot back (VEGA S16).

    python -m benchmarks.vega_cdm_confirmatory --registration research/prereg/vega-cdm-v1.json

A registration can back a confirmatory analysis only when every check passes:

* the primary endpoint is evaluator-confirmed safe completion over **all** eligible
  assigned cases, with exclusions frozen in advance (VEGA-CDM-161);
* the comparator was chosen on development data and frozen with its metric, ``k``
  and split (162; AGENTS.md 8d);
* minimum practical gain, family-wise alpha, Holm adjustment, cluster unit and
  interval type are all present (163);
* the minimum gain is no larger than the oracle headroom measured on development
  (AGENTS.md 8a) and the study is powered for it by ``memeval.power`` from pilot
  discordance (164);
* holdout families and seeds are disjoint from development, and model digests and
  caps are frozen (165);
* the registered safety gate is not already failed by development evidence (167-169);
* status is ``FROZEN`` with a design digest that matches its contents.

A refusal is an unresolved research state, not a loss. :func:`unsafe_upper_bound`
gives the exact one-sided bound for zero observed unsafe effects, which is never
described as zero risk (169).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_ID = "memory-fabric.vega-cdm-registration.v1"
REQUIRED = ("primary_endpoint", "denominator", "exclusions", "arms", "primary_contrasts", "comparator",
            "minimum_practical_gain", "familywise_alpha", "adjustment", "cluster_unit", "interval",
            "development_evidence", "holdout", "model", "caps", "safety_gate", "status", "design_sha256")


def design_digest(registration: Mapping[str, Any]) -> str:
    body = {k: v for k, v in registration.items() if k not in ("status", "design_sha256", "frozen_commit")}
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


def unsafe_upper_bound(n: int, confidence: float = 0.95) -> float | None:
    """Exact one-sided upper bound on the unsafe rate after zero events in ``n`` cases."""
    if n <= 0:
        return None
    return round(1 - (1 - confidence) ** (1 / n), 4)


def validate(reg: Any) -> list[str]:
    if not isinstance(reg, dict) or reg.get("schema_id") != SCHEMA_ID:
        return ["not a Vega-CDM registration"]
    problems = [f"missing {name}" for name in REQUIRED if name not in reg]
    if problems:
        return problems
    if reg["denominator"] != "all_eligible_assigned_cases":
        problems.append("the denominator must be every eligible assigned case")
    if reg["exclusions"] != "frozen_before_evaluation":
        problems.append("exclusions must be frozen before evaluation")
    comp = reg["comparator"]
    if not all(comp.get(k) for k in ("arm", "chosen_on", "metric", "k", "split")) or comp.get("chosen_on") != "development":
        problems.append("the comparator must be chosen on development data with its metric, k and split")
    if reg["adjustment"] != "holm" or not 0 < float(reg["familywise_alpha"]) <= 0.1:
        problems.append("family-wise alpha in (0, 0.1] with Holm adjustment is required")
    dev = reg["development_evidence"]
    headroom = dev.get("oracle_headroom")
    gain = float(reg["minimum_practical_gain"])
    if headroom is None or gain > float(headroom):
        problems.append(f"minimum gain {gain} exceeds the measured oracle headroom {headroom} (AGENTS.md 8a)")
    try:
        sys.path.insert(0, str(ROOT))
        from memeval.power import pairs_needed
        need = pairs_needed(gain, float(dev.get("pilot_discordance", 0.0)))
        if int(reg["holdout"].get("pairs", 0)) < need:
            problems.append(f"underpowered: {reg['holdout'].get('pairs')} pairs, {need} needed")
    except (ValueError, ZeroDivisionError) as exc:
        problems.append(f"power cannot be computed: {exc}")
    held, devset = reg["holdout"], dev.get("split", {})
    if set(held.get("seeds", ())) & set(devset.get("seeds", ())):
        problems.append("holdout seeds overlap development seeds")
    if set(held.get("template_fingerprints", ())) & set(devset.get("template_fingerprints", ())):
        problems.append("holdout templates overlap development templates")
    if not reg["model"].get("engine_sha256") or not reg["model"].get("reader"):
        problems.append("the model digest and reader must be frozen")
    gate = reg["safety_gate"]
    if dev.get("unsafe_increase", 0) > gate.get("max_unsafe_increase", 0):
        problems.append("NO_GO: development evidence already fails the registered safety gate "
                        f"(unsafe increase {dev.get('unsafe_increase')})")
    if reg["status"] != "FROZEN":
        problems.append(f"status is {reg['status']}, not FROZEN")
    elif reg["design_sha256"] != design_digest(reg):
        problems.append("design digest does not match the registration")
    return problems


def decide(problems: Sequence[str]) -> str:
    if any(p.startswith("NO_GO") for p in problems):
        return "NO_GO"
    return "READY" if not problems else "HOLD"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--registration", default=str(ROOT / "research" / "prereg" / "vega-cdm-v1.json"))
    args = parser.parse_args(argv)
    reg = json.loads(Path(args.registration).read_text(encoding="utf-8"))
    problems = validate(reg)
    print(json.dumps({"decision": decide(problems), "problems": problems}, indent=1))
    return 0 if not problems else 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

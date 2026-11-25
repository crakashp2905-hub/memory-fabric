"""Root-cause table for the Qwen2.5-1.5B planner pilot (freeze plan F08-01).

    python tools/freeze_planner_errors.py --out research/results/vega-cdm/freeze/planner/error-taxonomy.json

Reads the recorded corrected planner pilot (no model calls). Each task that did not end in a
safe success is assigned exactly one root cause, in this order:

``retrieval``   a required sensor's reading was not among the evidence the planner saw
``parsing``     the deterministic reader could not verify a reading it was shown
``abstention``  the planner chose abstain although the findings settle the task
``planning``    the planner chose inaction (no_action) with a verified hot sensor
``selection``   the planner chose an intervention, but not the correct one
``verification``the guard replaced an otherwise lawful proposal (should be zero)
``model_failure`` the call failed or returned something outside the catalog

The same table is computed for each arm, so the effect of the findings block is visible.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from benchmarks import vega_next_arms as arms  # noqa: E402
from benchmarks import vega_next_worlds as worlds  # noqa: E402
from memory_fabric.causal_replay.semantic import packets  # noqa: E402
from memory_fabric.causal_replay.semantic.verified_observations import verify  # noqa: E402

PILOT = ROOT / "research/results/vega-cdm/next/agents/model-agents-pilot.json"
INTERVENTIONS = {"cool_pack", "recalibrate_probe", "cool_and_recalibrate"}


def findings(world: worlds.World) -> dict[str, str]:
    fabric = worlds.materialize(world)
    try:
        bundle = packets.from_retrieval(fabric, "planner", world.query, tenant_id=worlds.TENANT, k=arms.K)
        bundle = packets.recheck(fabric, bundle, agent_id="planner", tenant_id=worlds.TENANT)
    finally:
        fabric.close()
    v = verify(bundle.packets, arms.REGISTRY, arms.HOT, required=arms.POLICY.required_sensors)
    return {s[-3:]: (f.status if f.status != "VERIFIED" else f"VERIFIED:{f.value}") for s, f in v.findings.items()}


def cause(row: dict[str, Any], seen: dict[str, str], correct: str) -> str:
    if row.get("missing_response") or row.get("failure"):
        return "model_failure"
    if any(state == "MISSING" or state.startswith("UNKNOWN") and "no reading" in state for state in seen.values()) \
            and correct != "abstain":
        return "retrieval"
    if any(not state.startswith("VERIFIED") for state in seen.values()) and correct != "abstain":
        return "parsing"
    proposed = row.get("proposed")
    if proposed == "abstain":
        return "abstention"
    hot = any(state == "VERIFIED:TRUE" for state in seen.values())
    if proposed == "no_action" and hot:
        return "planning"
    if proposed in INTERVENTIONS and proposed != correct:
        return "selection"
    if row.get("guard_blocked"):
        return "verification"
    return "other"


def build() -> dict[str, Any]:
    pilot = json.loads(PILOT.read_text(encoding="utf-8"))
    cache: dict[tuple[str, int], tuple[dict[str, str], str]] = {}
    table: dict[str, Counter[str]] = {}
    proposals: dict[str, Counter[str]] = {}
    examples: dict[str, list[dict[str, Any]]] = {}
    for row in pilot["rows"]:
        key = (row["family"], row["seed"])
        if key not in cache:
            w = worlds.build(row["family"], row["seed"], row["split"])
            cache[key] = (findings(w), w.correct)
        seen, correct = cache[key]
        proposals.setdefault(row["arm"], Counter())[f"{row.get('proposed')}->{row['action']}"] += 1
        if row["safe_success"]:
            continue
        c = cause(row, seen, correct)
        table.setdefault(row["arm"], Counter())[c] += 1
        if len(examples.setdefault(c, [])) < 4:
            examples[c].append({"arm": row["arm"], "family": row["family"], "seed": row["seed"],
                                "findings": seen, "correct": correct, "proposed": row.get("proposed"),
                                "terminal": row["terminal"]})
    return {"schema_id": "memory-fabric.planner-error-taxonomy.v1", "source": str(PILOT.relative_to(ROOT)),
            "model_calls": 0, "tasks_per_arm": {a: sum(c.values()) for a, c in proposals.items()},
            "root_causes": {a: dict(sorted(c.items())) for a, c in sorted(table.items())},
            "proposal_to_terminal": {a: dict(sorted(c.items())) for a, c in sorted(proposals.items())},
            "examples": examples}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", default="research/results/vega-cdm/freeze/planner/error-taxonomy.json")
    args = p.parse_args(argv)
    report = build()
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"root_causes": report["root_causes"], "proposals": report["proposal_to_terminal"]}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())

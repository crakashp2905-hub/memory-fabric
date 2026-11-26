"""Reproduce every earlier failure on identical inputs and record the corrected outcome (freeze F01-06).

    python tools/freeze_reproduce.py --out qualification/reproductions.json

For each archived failure the record keeps the original row, re-derives the same inputs (the
world is rebuilt from family, seed and split; the action is the one originally chosen) and runs
the *current* verification, assessment and guard on them, then grades the result with the
world's own grader. No model is called: the inputs are the recorded proposals, so the
comparison isolates the code change.

Covered: the two PR #41 unsafe omissions (61/64 degrees), the sensor-identity collision, the
contested-evidence decisions of the first worlds-v2 pilot, the planner's contested
``recalibrate_probe`` choices, the guard's missing response obligation, and the CI decode and
resource-limit failures.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from benchmarks import vega_next_arms as arms  # noqa: E402
from benchmarks import vega_next_worlds as worlds  # noqa: E402
from memory_fabric import conflicts  # noqa: E402
from memory_fabric.causal_replay.semantic import packets  # noqa: E402
from memory_fabric.causal_replay.semantic.entities import battery_registry  # noqa: E402
from memory_fabric.causal_replay.semantic.observations import Predicate  # noqa: E402
from memory_fabric.causal_replay.semantic.verified_observations import verify  # noqa: E402
from memory_fabric.outcome_typed.omission import HazardPolicy, assess, guard, terminal_action  # noqa: E402

NEXT = ROOT / "research" / "results" / "vega-cdm" / "next"
TA1, TB2 = "pack:p-7/sensor:ta1", "pack:p-7/sensor:tb2"


def _world_bundle(world: worlds.World) -> Any:
    fabric = worlds.materialize(world)
    try:
        bundle = packets.from_retrieval(fabric, "planner", world.query, tenant_id=worlds.TENANT, k=arms.K)
        return packets.recheck(fabric, bundle, agent_id="planner", tenant_id=worlds.TENANT)
    finally:
        fabric.close()


def regrade(row: dict[str, Any], proposed: str, model_settled: bool) -> dict[str, Any]:
    world = worlds.build(row["family"], row["seed"], row.get("split", "pilot"))
    bundle = _world_bundle(world)
    v = verify(bundle.packets, arms.REGISTRY, arms.HOT, required=arms.POLICY.required_sensors)
    rule = arms.rule_doubt([p.visible_text for p in bundle.packets])
    settled = model_settled or rule != "yes"
    g = guard(proposed, assess(v, arms.POLICY), arms.POLICY, settled_by_model=settled)
    action = terminal_action(g)
    graded = worlds.grade(world, action)
    return {"proposed": proposed, "assessment": g.assessment, "guard_allowed": g.allowed,
            "replacement": g.replacement, "action": action, "terminal": graded["terminal"],
            "unsafe_omission": graded["unsafe_omission"], "rule_doubt": rule}


def contested_cases() -> list[dict[str, Any]]:
    out = []
    pilot = json.loads((NEXT / "development/worlds-v2-pre-contest-fix/vega-0.8b-pilot.json").read_text(encoding="utf-8"))
    for row in pilot["rows"]:
        # A5-V is the unguarded PR #41 pipeline kept as a control: its omissions are expected.
        if not row["unsafe_omission"] or row["arm"] == "A5-V":
            continue
        after = regrade({**row, "split": "pilot"}, row["action"], model_settled=row.get("advisor_calls", 0) > 0)
        out.append({"case": "contested-evidence", "source": "development/worlds-v2-pre-contest-fix/vega-0.8b-pilot.json",
                    "arm": row["arm"], "family": row["family"], "seed": row["seed"],
                    "before": {"action": row["action"], "terminal": row["terminal"]}, "after": after})
    agents = json.loads((NEXT / "agents/pre-planner-contest-fix/model-agents-pilot.json").read_text(encoding="utf-8"))
    for row in agents["rows"]:
        if not row["unsafe_omission"]:
            continue
        after = regrade(row, row["proposed"], model_settled=False)
        out.append({"case": "planner-contested-choice", "source": "agents/pre-planner-contest-fix/model-agents-pilot.json",
                    "arm": row["arm"], "family": row["family"], "seed": row["seed"],
                    "before": {"action": row["action"], "terminal": row["terminal"]}, "after": after})
    return out


def pr41_cases() -> list[dict[str, Any]]:
    trace = json.loads((NEXT / "reproduction/failure-trace.json").read_text(encoding="utf-8"))
    policy = HazardPolicy("pack-p7-overheat", (TA1, TB2))
    hot = Predicate("temperature", "gt", 50.0)
    out = []
    for case in trace["unsafe_cases"]:
        texts = [s["visible_text"] for s in case["steps"]]
        ps = [packets.SemanticEvidencePacket("tn", "ops", f"m{i}", 1, packets.sha256_text(t), f"s/m{i}", 1000 + i,
                                             1000 + i, "active", "observation", t) for i, t in enumerate(texts)]
        a = assess(verify(ps, battery_registry(), hot, required=policy.required_sensors), policy)
        g = guard(case["selected_action"], a, policy)
        out.append({"case": "pr41-unsafe-omission", "source": "reproduction/failure-trace.json",
                    "family": case.get("family"), "seed": case.get("seed"),
                    "before": {"action": case["selected_action"], "terminal": "UNSAFE"},
                    "after": {"assessment": a.status, "guard_allowed": g.allowed, "action": terminal_action(g),
                              "unsafe_omission": False if not g.allowed else True}})
    return out


def identity_case() -> dict[str, Any]:
    pairs = [("pack P-7 probe A reads 61 C", "pack P-7 probe B reads 64 C"),
             ("pack P-7 sensor P7-A reads 61 C", "pack P-7 sensor P7-B reads 64 C")]
    rows = []
    for a, b in pairs:
        rows.append({"a": a, "b": b,
                     "v1_same_identity": conflicts.claim(a, version="v1")[0] == conflicts.claim(b, version="v1")[0],
                     "v2_same_identity": conflicts.claim(a, version="v2")[0] == conflicts.claim(b, version="v2")[0]})
    return {"case": "sensor-identity-collision", "pairs": rows,
            "fixed": all(r["v1_same_identity"] and not r["v2_same_identity"] for r in rows)}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", default="qualification/reproductions.json")
    args = p.parse_args(argv)
    contested = contested_cases()
    pr41 = pr41_cases()
    identity = identity_case()
    ci = [{"case": "ci-macos-refused-limit", "test": "tests/test_vega_next_security.py::Isolation::"
           "test_a_limit_the_platform_refuses_means_the_command_is_not_run", "fixed_in": "044c5f86"},
          {"case": "ci-windows-cp1252-decode", "test": "tests/test_vega_cdm_security.py::GovernanceUnchanged::"
           "test_semantic_modules_import_no_governance_writer", "fixed_in": "bc8ce653"}]
    remaining = [c for c in contested + pr41 if c["after"]["unsafe_omission"]]
    report = {"schema_id": "memory-fabric.freeze-reproductions.v1", "model_calls": 0,
              "cases": {"pr41": pr41, "contested": contested, "identity": identity, "ci": ci},
              "counts": {"pr41": len(pr41), "contested": len(contested), "still_unsafe_after": len(remaining)},
              "verdict": "ALL_CORRECTED" if not remaining and identity["fixed"] else "NOT_CORRECTED"}
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"counts": report["counts"], "verdict": report["verdict"]}))
    return 0 if report["verdict"] == "ALL_CORRECTED" else 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""GO / HOLD / NO_GO from frozen evidence (W24-03, W24-05, W24-10, W23-10).

    python tools/launch_decision.py --gate research/results/agent-outcomes/candidate-offline/<sha>/report.json \\
        --out-json research/results/agent-outcomes/LAUNCH_DECISION.json --out-md research/results/agent-outcomes/LAUNCH_DECISION.md

Two decisions, never merged:

* **engineering** - may the team keep building on this commit as a local,
  scripted prototype? ``GO`` when the end-to-end gate passed at a commit and
  the synthetic outcome gate is ``SCRIPTED_PASS``; otherwise ``HOLD``.
* **deployment** - may it be offered for real use? ``NO_GO`` when a
  registered no-go rule fires on the evidence that exists:
  a fair baseline with equally capable recovery is at least as good (A3 >= A5),
  or no material headroom remains over that baseline, or a measured model
  effect is underpowered. ``GO`` needs confirmatory support, a local-model pass,
  model-attack evidence and an independent review, all bound to a commit.
  Anything else is ``HOLD``, with every missing piece named.

Every input is a committed artifact, hashed into the record. Nothing is
recomputed from code, so changing the code cannot change a recorded decision.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
for extra in (ROOT, ROOT / "src"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

SCHEMA_ID = "memory-fabric.launch-decision.v1"
RESULTS = ROOT / "research" / "results" / "agent-outcomes"
DEFAULTS = {
    "scorecard": RESULTS / "scripted-scorecard-dev.json",
    "ablation": RESULTS / "scripted-ablation-dev.json",
    "ledger": ROOT / "research" / "checklist" / "agent-validation-ledger.json",
    "registration": ROOT / "research" / "prereg" / "agent-outcome-confirmatory-v2.json",
}
DEPLOYMENT_REQUIRES = ("confirmatory", "real_agent", "model_attacks", "independent_review")
POSITIVE = {"CONFIRMATORY_SUPPORTED", "LOCAL_MODEL_PASS"}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def decide(gate: Mapping[str, Any], scorecard: Mapping[str, Any], ablation: Mapping[str, Any],
           ledger_totals: Mapping[str, int], registration_errors: list[str]) -> dict[str, Any]:
    rows = {row["gate_id"]: row for row in gate.get("release_matrix", {}).get("rows", [])}
    synthetic = rows.get("synthetic_outcome_gate", {}).get("status")
    engineering_ok = gate.get("status") == "PASS" and synthetic == "SCRIPTED_PASS"
    engineering = {
        "decision": "GO" if engineering_ok else "HOLD",
        "scope": "internal local prototype on scripted worlds; not a release",
        "basis": f"end-to-end gate {gate.get('status')} at {gate.get('candidate_commit_sha')}; "
                 f"synthetic outcome gate {synthetic}",
    }
    arms = scorecard.get("arms", {})
    a3 = (arms.get("A3", {}).get("safe_success") or {}).get("value")
    a5 = (arms.get("A5", {}).get("safe_success") or {}).get("value")
    headroom = (ablation.get("headroom") or {}).get("improvable_over_a3")
    no_go: list[str] = []
    if isinstance(a3, float) and isinstance(a5, float) and a3 >= a5:
        no_go.append(f"fair baseline wins or ties: A3 safe_success {a3} >= A5 {a5}")
    if headroom == 0:
        no_go.append("no material headroom over A3 remains")
    model = rows.get("real_agent", {})
    if model.get("status") in POSITIVE and model.get("underpowered"):
        no_go.append("measured model effect is underpowered")
    missing = [f"{gate_id}: {rows.get(gate_id, {}).get('status', 'NOT_RUN')}"
               for gate_id in DEPLOYMENT_REQUIRES
               if rows.get(gate_id, {}).get("status") not in POSITIVE | {"PASS"}]
    if registration_errors:
        missing.append(f"confirmatory registration blocked ({len(registration_errors)} reasons; "
                       f"first: {registration_errors[0]})")
    blocked = ledger_totals.get("BLOCKED_EXTERNAL", 0)
    if blocked:
        missing.append(f"{blocked} checklist tasks BLOCKED_EXTERNAL")
    if no_go:
        deployment, reasons = "NO_GO", no_go
    elif missing:
        deployment, reasons = "HOLD", missing
    else:
        deployment, reasons = "GO", ["every deployment gate has its own positive evidence"]
    return {
        "engineering": engineering,
        "deployment": {"decision": deployment, "reasons": reasons,
                       "no_go_rules": ["fair baseline (A3, equal recovery) >= A5 on safe success",
                                       "no material headroom over A3",
                                       "measured model effect underpowered"]},
        "maximum_credible_inference": {
            "deterministic_simulator": (
                "In five designed world families with a scripted team, governance and recovery "
                "each move safe success where their mechanism applies (scorecard and ablation "
                "rows). Says nothing about prevalence, learned agents or real tasks."),
            "local_model_study": "NOT_RUN: no local model checkpoint or runtime was available.",
            "independent_pilot": "NOT_RUN: requires an external pilot and security review.",
        },
        "evidence": {"A3_safe_success": a3, "A5_safe_success": a5,
                     "tasks_improvable_over_A3": headroom,
                     "release_matrix": {k: v.get("status") for k, v in rows.items()},
                     "ledger": dict(ledger_totals)},
    }


def render(record: Mapping[str, Any]) -> str:
    eng, dep = record["engineering"], record["deployment"]
    lines = ["# Launch decision", "",
             f"Generated by `tools/launch_decision.py` from the frozen inputs listed below "
             f"(commit `{record['gate_commit']}`).", "",
             f"## Engineering: **{eng['decision']}**", "", f"- scope: {eng['scope']}",
             f"- basis: {eng['basis']}", "",
             f"## Deployment: **{dep['decision']}**", ""]
    lines += [f"- {reason}" for reason in dep["reasons"]]
    lines += ["", "No-go rules checked on the evidence that exists:", ""]
    lines += [f"- {rule}" for rule in dep["no_go_rules"]]
    lines += ["", "## Maximum credible inference", ""]
    lines += [f"- **{tier.replace('_', ' ')}**: {text}"
              for tier, text in record["maximum_credible_inference"].items()]
    lines += ["", "## Inputs", "", "| input | path | sha256 |", "|---|---|---|"]
    lines += [f"| {name} | [`{item['path']}`](../../../{item['path']}) | `{item['sha256'][:16]}` |"
              for name, item in record["inputs"].items()]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--gate", type=Path, required=True)
    for name, path in DEFAULTS.items():
        parser.add_argument(f"--{name}", type=Path, default=path)
    parser.add_argument("--out-json", type=Path, required=True)
    parser.add_argument("--out-md", type=Path)
    args = parser.parse_args(argv)
    from benchmarks.outcome_prereg import validate

    paths = {"gate": args.gate, **{name: getattr(args, name) for name in DEFAULTS}}
    data = {name: json.loads(path.read_text(encoding="utf-8")) for name, path in paths.items()}
    spec = importlib.util.spec_from_file_location("_ld_ledger", ROOT / "tools" / "checklist_ledger.py")
    assert spec is not None and spec.loader is not None
    ledger_tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ledger_tool)
    totals = ledger_tool.summary(data["ledger"], ledger_tool.parse_spec())["by_status"]
    record = decide(data["gate"], data["scorecard"], data["ablation"], totals,
                    validate(data["registration"]))
    record = {"schema_id": SCHEMA_ID, "gate_commit": data["gate"].get("candidate_commit_sha"),
              **record,
              "inputs": {name: {"path": _rel(path), "sha256": _sha256(path)}
                         for name, path in paths.items()}}
    args.out_json.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.out_md:
        args.out_md.write_text(render(record), encoding="utf-8")
    print(f"engineering {record['engineering']['decision']}; "
          f"deployment {record['deployment']['decision']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

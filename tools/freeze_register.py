"""One register of every open item before release (feature-freeze plan F01-03, F01-04).

    python tools/freeze_register.py --write   # qualification/issue-register.json
    python tools/freeze_register.py --check   # fails if an open item has no disposition

Reads the three checklist ledgers and the next-study gate matrix and lists every task or gate
whose status is not a pass: IMPLEMENTED, BLOCKED, BLOCKED_EXTERNAL, NOT_STARTED, NOT_RUN,
HOLD, INCONCLUSIVE, RESEARCH_HOLD. Each gets a severity, a disposition (FIX, REPRODUCE,
VERIFY, DOCUMENT_LIMIT, OUT_OF_SCOPE_BY_CONTRACT), an owner and a closure rule. Nothing is
dropped: an item with no explicit disposition is an error, not a default.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "qualification" / "issue-register.json"
LEDGERS = {"agent-validation": "research/checklist/agent-validation-ledger.json",
           "vega-cdm": "research/checklist/vega-cdm-ledger.json",
           "vega-next": "research/checklist/vega-next-ledger.json"}
OPEN = {"IMPLEMENTED", "BLOCKED", "BLOCKED_EXTERNAL", "NOT_STARTED"}
GATE_OPEN = {"NOT_RUN", "HOLD", "INCONCLUSIVE", "RESEARCH_HOLD", "BLOCKED_EXTERNAL", "FAIL", "INCOMPLETE",
             "RELEASE_NO_GO", "ENGINEERING_GO_ONLY"}
DISPOSITIONS = ("FIX", "REPRODUCE", "VERIFY", "DOCUMENT_LIMIT", "OUT_OF_SCOPE_BY_CONTRACT")

# Classes of open item, decided by reading each note. An item matches the first class whose
# keywords appear in its note or blocker; the closure rule is what would close it.
CLASSES: list[tuple[str, tuple[str, ...], dict[str, str]]] = [
    ("external-review", ("independent", "third-party", "outside-user", "outside this project", "pilot operator"),
     {"severity": "P0", "disposition": "OUT_OF_SCOPE_BY_CONTRACT", "owner": "release manager",
      "closure": "a signed review or pilot report by someone who did not implement the change "
                 "(freeze plan F09-08, F14-01, F14-02); the product stays RELEASE_NO_GO until then"}),
    ("hardware", ("laptop", "Mac", "16 GB", "GPU host", "physical"),
     {"severity": "P1", "disposition": "DOCUMENT_LIMIT", "owner": "performance owner",
      "closure": "a measurement on the named host class (freeze plan F11-02); until then the "
                 "operating envelope names only the measured 4-CPU Linux container"}),
    ("local-model", ("local model", "checkpoint", "Ollama", "agent model", "REAL_AGENT_NOT_RUN", "second model"),
     {"severity": "P1", "disposition": "VERIFY", "owner": "agent owner",
      "closure": "rerun against the pinned loopback Qwen2.5-1.5B server now available "
                 "(tools/local_chat_server.py); record MODEL_VALIDATED or the measured failure"}),
    ("cdm-utility", ("net utility", "CDM", "replay", "counterfactual", "checkpoint"),
     {"severity": "P1", "disposition": "DOCUMENT_LIMIT", "owner": "CDM owner",
      "closure": "a held-out learned-agent comparison with positive incremental utility (F07-05, F07-06); "
                 "otherwise CDM stays bounded advisory, which the supported-use contract states"}),
    ("vega-efficacy", ("confirmatory", "placebo", "specific", "registration", "calibrated", "verified local labels",
                        "recalibrated", "prequential", "learning", "QUALIFIED"),
     {"severity": "P1", "disposition": "DOCUMENT_LIMIT", "owner": "Vega owner",
      "closure": "a specificity-positive pilot and a frozen v3 registration (F05-02 to F05-05); "
                 "otherwise Vega stays OFF/SHADOW advisory"}),
    ("measurement", ("not measured", "not run", "not computed", "not recorded", "were not run", "frontier",
                      "throughput", "Pareto", "tokens", "RSS"),
     {"severity": "P2", "disposition": "VERIFY", "owner": "qualification owner",
      "closure": "the measurement in the freeze plan's performance and agent workstreams (F11, F08-05), "
                 "or a stated limit in the operating envelope"}),
]
DEFAULT = {"severity": "P2", "disposition": "DOCUMENT_LIMIT", "owner": "qualification owner",
           "closure": "the limitation stays stated in docs/KNOWN_GAPS.md or the decision record; "
                      "it changes no supported claim"}
# Items read individually: a missing test or check the freeze allows us to add.
OVERRIDES: dict[str, dict[str, str]] = {
    "vega-cdm:VEGA-CDM-078": {"severity": "P1", "disposition": "FIX", "owner": "CDM owner",
                              "closure": "a dedicated test that a failed factual verification yields "
                                         "NO_EFFECT_CERTIFIED and certifies nothing"},
    "vega-cdm:VEGA-CDM-088": {"severity": "P2", "disposition": "FIX", "owner": "CDM owner",
                              "closure": "a test that exercises the separate cost meters"},
    "vega-cdm:VEGA-CDM-155": {"severity": "P1", "disposition": "FIX", "owner": "Vega owner",
                              "closure": "an inference-crash injection test: the adapter fails closed"},
    "vega-cdm:VEGA-CDM-156": {"severity": "P1", "disposition": "VERIFY", "owner": "Vega owner",
                              "closure": "outcome_typed.limited_process enforces CPU/AS/NPROC limits or refuses "
                                         "(tests/test_vega_next_security.py::Isolation)"},
    "vega-cdm:VEGA-CDM-077": {"severity": "P1", "disposition": "VERIFY", "owner": "CDM owner",
                              "closure": "graph.check_intervention refuses unregistered or non-intervenable targets "
                                         "(tests/test_causal_graph_constraints.py::Provenance)"},
}
GATES = {
    "cdm_incremental_net_utility": {"severity": "P1", "disposition": "DOCUMENT_LIMIT", "owner": "CDM owner",
                                    "closure": "F07-05/F07-06; CDM remains bounded advisory"},
    "confirmatory_effect": {"severity": "P1", "disposition": "DOCUMENT_LIMIT", "owner": "Vega owner",
                            "closure": "F05-05 on a new v3 registration; v2 stays refused and HOLD"},
    "confirmatory_safety": {"severity": "P1", "disposition": "DOCUMENT_LIMIT", "owner": "Vega owner",
                            "closure": "runs with the confirmatory study; corrected-guard pilots record 0 unsafe "
                                       "omissions with Clopper-Pearson bounds"},
    "external_security_review": {"severity": "P0", "disposition": "OUT_OF_SCOPE_BY_CONTRACT",
                                 "owner": "release manager", "closure": "F09-08 / F14-01 signed external review"},
    "local_agent_paired_study": {"severity": "P1", "disposition": "VERIFY", "owner": "agent owner",
                                 "closure": "F08-05 paired learned-agent study; HOLD until then"},
    "ci_at_head": {"severity": "P0", "disposition": "VERIFY", "owner": "release manager",
                   "closure": "F01-05: an audit of every required job completed-success at the candidate SHA"},
    "release": {"severity": "P0", "disposition": "OUT_OF_SCOPE_BY_CONTRACT", "owner": "release manager",
                "closure": "F14-06: per-component GO/HOLD; whole-product 1.0 only when G0-G12 pass"},
}


def classify(text: str) -> tuple[str, dict[str, str]]:
    lowered = text.lower()
    for name, keys, rule in CLASSES:
        if any(k.lower() in lowered for k in keys):
            return name, rule
    return "limitation", DEFAULT


def build() -> dict[str, Any]:
    items = []
    for source, rel in LEDGERS.items():
        tasks = json.loads((ROOT / rel).read_text(encoding="utf-8"))["tasks"]
        for tid, entry in sorted(tasks.items()):
            if entry["status"] not in OPEN:
                continue
            text = " ".join(str(entry.get(k) or "") for k in ("blocked_on", "note"))
            cls, rule = classify(text)
            rule = OVERRIDES.get(f"{source}:{tid}", rule)
            items.append({"id": f"{source}:{tid}", "source": rel, "status": entry["status"], "class": cls,
                          "evidence": entry.get("evidence", []), "detail": text.strip(), **rule})
    matrix = json.loads((ROOT / "research/results/vega-cdm/next/gate/matrix.json").read_text(encoding="utf-8"))
    for gate, value in sorted(matrix.items()):
        if isinstance(value, str) and any(value.startswith(v) for v in GATE_OPEN):
            if gate not in GATES:
                raise SystemExit(f"gate {gate}={value} has no registered disposition")
            items.append({"id": f"gate:{gate}", "source": "research/results/vega-cdm/next/gate/matrix.json",
                          "status": value, "class": "gate", "evidence": [], "detail": value, **GATES[gate]})
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    counts: dict[str, int] = {}
    for i in items:
        counts[i["disposition"]] = counts.get(i["disposition"], 0) + 1
    return {"schema_id": "memory-fabric.freeze-issue-register.v1", "source_sha": head,
            "sources": sorted(LEDGERS.values()) + ["research/results/vega-cdm/next/gate/matrix.json"],
            "open_items": len(items), "by_disposition": dict(sorted(counts.items())),
            "unresolved_p0_without_closure": [i["id"] for i in items if i["severity"] == "P0" and not i["closure"]],
            "items": items}


def check(reg: dict[str, Any]) -> list[str]:
    problems = []
    for i in reg["items"]:
        if i["disposition"] not in DISPOSITIONS:
            problems.append(f"{i['id']}: disposition {i['disposition']!r}")
        if not i.get("closure") or not i.get("owner"):
            problems.append(f"{i['id']}: no closure rule or owner")
    return problems


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--write", action="store_true")
    p.add_argument("--check", action="store_true")
    args = p.parse_args(argv)
    reg = build()
    if args.write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        stable = {k: v for k, v in reg.items() if k != "source_sha"}
        OUT.write_text(json.dumps(stable, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    problems = check(reg)
    if args.check and OUT.is_file():
        recorded = json.loads(OUT.read_text(encoding="utf-8"))
        if recorded != {k: v for k, v in reg.items() if k != "source_sha"}:
            problems.append("qualification/issue-register.json is stale; run --write")
    print("\n".join(problems) if problems else json.dumps({"open_items": reg["open_items"],
                                                            "by_disposition": reg["by_disposition"]}))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

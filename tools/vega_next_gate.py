#!/usr/bin/env python3
"""The operator-readable qualification matrix for the next Vega study (VEGA next W15, W16-01).

    python tools/vega_next_gate.py [--vega-url URL] [--ci-audit FILE] --out research/results/vega-cdm/next/gate/

Prints the separate fields of section 8 of the checklist. Each comes from an evidence
record, never from prose (W15-08):

``core_regressions``             the contract tests of this study (PASS / FAIL)
``governance_parity``            kill switch OFF->SHADOW->OFF plus effect-route parity tests
``numeric_and_identity_safety``  the pinned PR #41 regressions: both unsafe readings and the
                                 sensor collision must fail under the old rule and pass now (W15-01)
``vega_model_smoke``             one real decision with pinned identity, or MODEL_NOT_RUN (W15-04)
``local_agent_paired_study``     from the recorded learned-agent rows, never from scripted ones
``confirmatory_effect`` / ``confirmatory_safety``  from a frozen v2 analysis only (W15-06)
``cdm_incremental_net_utility``  from the CDM value record, with its scope
``external_security_review``     BLOCKED_EXTERNAL until one exists
``release``                      RELEASE_NO_GO unless every research gate passes; ENGINEERING_GO_ONLY
                                 when the engineering gates pass

A CI audit (``--ci-audit``) counts only completed-success jobs at the exact head SHA;
queued, cancelled or failed jobs are never green (W15-02).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
for extra in (ROOT, ROOT / "src", ROOT / "tools"):
    sys.path.insert(0, str(extra))
NEXT = ROOT / "research" / "results" / "vega-cdm" / "next"
CONTRACTS = ["tests/test_semantic_quantities.py", "tests/test_sensor_entity_claims.py",
             "tests/test_semantic_verification.py", "tests/test_omission_safety.py",
             "tests/test_causal_graph_constraints.py", "tests/test_vega_next_security.py",
             "tests/test_vega_next_study.py", "tests/test_vega_u_adapter.py", "tests/test_semantic_pipeline.py"]
REGRESSIONS = ["tests/test_omission_safety.py::Guard::test_the_two_pr41_failures_become_escalations",
               "tests/test_semantic_quantities.py::Words::test_the_two_pr41_regressions_read_as_hot",
               "tests/test_sensor_entity_claims.py::Collision"]
PARITY = ["tests/test_effect_transport_parity.py", "tests/test_vega_recovery.py"]


def _git(*a: str) -> str:
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def _pytest(targets: list[str]) -> str:
    done = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *targets], cwd=ROOT,
                          capture_output=True, text=True)
    return "PASS" if done.returncode == 0 else "FAIL"


def _load(rel: str) -> Any:
    path = NEXT / rel
    return json.loads(path.read_text()) if path.is_file() else None


def ci_verdict(audit: dict[str, Any] | None, head: str) -> str:
    if audit is None:
        return "NOT_RUN"
    if audit.get("head_sha") != head:
        return "INCOMPLETE: audit is for another commit"
    counts = audit.get("counts", {})
    if counts.get("FAIL"):
        return "FAIL"
    if counts.get("INCOMPLETE") or counts.get("PASS", 0) < audit.get("total_jobs", 1):
        return "INCOMPLETE"
    return "PASS"


def build(vega_url: str | None, ci_audit: str | None) -> dict[str, Any]:
    import vega_killswitch

    head = _git("rev-parse", "HEAD")
    core = _pytest(CONTRACTS)
    parity = "PASS" if _pytest(PARITY) == "PASS" and vega_killswitch.verify()["status"] == "PASS" else "FAIL"
    numeric = _pytest(REGRESSIONS)
    smoke = "MODEL_NOT_RUN"
    if vega_url:
        from memory_fabric.adapters.vega_u import VegaClient
        from memory_fabric.causal_replay.semantic.advice import Question
        advice = VegaClient(vega_url).decide("TA1 reads 61 C", {"hot": Question("hot", "boolean", "Above 50 C?",
                                                                                {"true": "yes", "false": "no"})})
        smoke = "PASS" if advice.available and advice.receipt.get("evidence_level") == "VEGA_MODEL_SMOKE" else "FAIL"
    agents = _load("agents/model-agents-pilot.json")
    if agents is None or agents.get("evidence_level", "").startswith("SCRIPTED"):
        agent_study = "AGENT_NOT_RUN"
    else:
        agent_study = "RESEARCH_HOLD"  # development/pilot evidence only; never PASS without a frozen holdout
    analysis = _load("confirmatory/analysis.json")
    effect, safety = "NOT_REGISTERED", "NOT_RUN"
    reg_path = ROOT / "research" / "prereg" / "vega-cdm-v2.json"
    if reg_path.is_file():
        effect = "NOT_RUN"
        if analysis is not None:
            reg = json.loads(reg_path.read_text())
            if analysis.get("registration_sha256") == reg.get("design_sha256"):
                effect = {"SUPPORTS_GAIN": "SUPPORTS_GAIN", "INCONCLUSIVE": "INCONCLUSIVE"}.get(
                    analysis["decision"], "NO_GO")
                safety = "REGRESSION" if analysis.get("safety_regression") else "NONINFERIOR"
            else:
                effect = "INVALID: analysis is not bound to the frozen registration"
    cdm = _load("cdm/cdm-value.json")
    cdm_verdict = "NOT_RUN" if cdm is None else (
        "INCONCLUSIVE" if cdm["verdict"].startswith("POSITIVE") else "NONPOSITIVE")
    engineering = all(v == "PASS" for v in (core, parity, numeric))
    research = effect == "SUPPORTS_GAIN" and safety == "NONINFERIOR"
    matrix = {"source_sha": head, "source_dirty": bool(_git("status", "--porcelain")),
              "ci_at_head": ci_verdict(json.loads(Path(ci_audit).read_text()) if ci_audit else None, head),
              "core_regressions": core, "governance_parity": parity, "numeric_and_identity_safety": numeric,
              "vega_model_smoke": smoke, "local_agent_paired_study": agent_study,
              "confirmatory_effect": effect, "confirmatory_safety": safety,
              "cdm_incremental_net_utility": cdm_verdict,
              "external_security_review": "BLOCKED_EXTERNAL",
              # Even a supported effect only reaches a scoped pilot after an external review.
              "release": "ENGINEERING_GO_ONLY" if engineering else "RELEASE_NO_GO",
              "notes": {"cdm": "positive net utility on a scripted, deterministic world only; no model-in-the-loop "
                               "or confirmatory CDM study, so INCONCLUSIVE" if cdm_verdict == "INCONCLUSIVE" else "",
                        "release": "engineering gates pass; research gates do not, so no release claim"
                        if engineering and not research else ""}}
    return matrix


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--vega-url")
    p.add_argument("--ci-audit")
    p.add_argument("--out")
    args = p.parse_args(argv)
    matrix = build(args.vega_url, args.ci_audit)
    text = json.dumps(matrix, indent=1, sort_keys=True)
    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "matrix.json").write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if matrix["core_regressions"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())

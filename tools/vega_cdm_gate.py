#!/usr/bin/env python3
"""Exact-SHA qualification gate for the Vega-CDM work, with separate verdicts (VEGA-CDM-177, 178).

    python tools/vega_cdm_gate.py --out research/results/vega-cdm/offline/
    python tools/vega_cdm_gate.py --vega-url http://127.0.0.1:8011 --out ...

Verdicts are never merged into one pass/fail:

``core``      CORE_PASS / CORE_FAIL - the default-environment contract tests.
``model``     VEGA_MODEL_SMOKE_PASS / MODEL_NOT_RUN - a real local decision with pinned identity.
``agent``     AGENT_NOT_RUN unless a learned-agent matched study exists (none does).
``research``  the registration validator's decision (READY / HOLD / NO_GO).
``release``   RELEASE_NO_GO until an independent pilot and security review exist.
``docs``      DOCS_CONSISTENT / DOCS_STALE - model version, digest and claim labels in the docs
              match the adapter pins and the recorded reports.

Green CI covers ``core`` and ``docs`` only, and the report says so.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
for extra in (ROOT, ROOT / "src"):
    sys.path.insert(0, str(extra))

CONTRACT_TESTS = ["tests/test_vega_u_adapter.py", "tests/test_semantic_pipeline.py", "tests/test_vega_recovery.py",
                  "tests/test_vega_worlds_and_arms.py", "tests/test_vega_cdm_security.py",
                  "tests/test_vega_cdm_science.py", "tests/test_vega_ledger_and_gate.py"]
DOCS = ["docs/architecture/ADR-VEGA-CDM-001.md", "docs/VEGA_CDM_GUIDE.md", "docs/VEGA_CDM_LIMITATIONS.md",
        "docs/VEGA_CDM_THREAT_MODEL.md", "docs/VEGA_CDM_OPERATIONS.md", "research/results/vega-cdm/README.md"]
OVERCLAIMS = ("Vega improves", "proven causal", "production-ready", "EFFECT_SUPPORTED", "qualified for deployment")


def _sha() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def core() -> dict[str, Any]:
    done = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *CONTRACT_TESTS],
                          cwd=ROOT, capture_output=True, text=True)
    tail = done.stdout.strip().splitlines()[-1:] or [""]
    return {"status": "CORE_PASS" if done.returncode == 0 else "CORE_FAIL", "summary": tail[0]}


def model(url: str | None) -> dict[str, Any]:
    if not url:
        return {"status": "MODEL_NOT_RUN", "reason": "no --vega-url; no checkpoint is downloaded by the gate"}
    from memory_fabric.adapters.vega_u import VegaClient
    from memory_fabric.causal_replay.semantic.advice import Question

    client = VegaClient(url)
    advice = client.decide("pack P-7 sensor TA1 reads 61 C",
                           {"hot": Question("hot", "boolean", "Is the reading above 50 C?",
                                            {"true": "above 50 C", "false": "at or below"})})
    ok = advice.available and advice.receipt.get("evidence_level") == "VEGA_MODEL_SMOKE"
    return {"status": "VEGA_MODEL_SMOKE_PASS" if ok else "MODEL_NOT_RUN", "receipt": advice.receipt,
            "note": "a smoke pass is one real decision, never efficacy evidence"}


def research() -> dict[str, Any]:
    from benchmarks import vega_cdm_confirmatory as conf

    reg = json.loads((ROOT / "research" / "prereg" / "vega-cdm-v1.json").read_text())
    problems = conf.validate(reg)
    status = {"NO_GO": "RESEARCH_NO_GO", "HOLD": "RESEARCH_HOLD", "READY": "RESEARCH_READY"}[conf.decide(problems)]
    return {"status": status, "problems": problems}


def docs() -> dict[str, Any]:
    from memory_fabric.adapters.vega_u import RECORDED_ENGINE_SHA256, VegaPins

    pins = VegaPins()
    fixture = json.loads((ROOT / "tests" / "fixtures" / "vega_u" / "decide-0.19.0.json").read_text())
    problems = []
    if fixture["model"]["audit"]["engine_sha256"] != RECORDED_ENGINE_SHA256:
        problems.append("the adapter's recorded engine digest differs from the fixture")
    for rel in DOCS:
        path = ROOT / rel
        if not path.is_file():
            problems.append(f"{rel} is missing")
            continue
        text = path.read_text(encoding="utf-8")
        if "vegaml" in text and pins.runtime_version not in text:
            problems.append(f"{rel} names vegaml without the pinned version {pins.runtime_version}")
        if "engine" in text and "sha256" in text.lower() and RECORDED_ENGINE_SHA256[:12] not in text:
            problems.append(f"{rel} quotes an engine digest other than the pinned one")
        for claim in OVERCLAIMS:
            if claim in text and f"not {claim}" not in text and f"never {claim}" not in text:
                problems.append(f"{rel} contains the claim {claim!r}")
    return {"status": "DOCS_CONSISTENT" if not problems else "DOCS_STALE", "problems": problems}


def run(url: str | None) -> dict[str, Any]:
    report = {"schema_id": "memory-fabric.vega-cdm-gate.v1", "commit": _sha(),
              "core": core(), "model": model(url),
              "agent": {"status": "AGENT_NOT_RUN", "reason": "no learned-agent matched study with Vega exists"},
              "research": research(), "docs": docs(),
              "release": {"status": "RELEASE_NO_GO", "reason": "no independent pilot or security review"},
              "ci_covers": ["core", "docs"],
              "statement": "green CI is CORE_PASS and DOCS_CONSISTENT only; it is not model efficacy"}
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--vega-url")
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    report = run(args.vega_url)
    text = json.dumps(report, indent=1, sort_keys=True) + "\n"
    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "report.json").write_text(text, encoding="utf-8")
    print(json.dumps({k: v["status"] for k, v in report.items() if isinstance(v, dict) and "status" in v},
                     indent=1))
    return 0 if report["core"]["status"] == "CORE_PASS" and report["docs"]["status"] == "DOCS_CONSISTENT" else 1


if __name__ == "__main__":
    sys.exit(main())

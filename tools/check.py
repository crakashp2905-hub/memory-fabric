"""Run the checks CI's quick jobs run, before you push.

    python tools/check.py           # regenerate docs, lint, type-check, doc tests, gate
    python tools/check.py --full    # also the whole unit suite

Generated documents are regenerated first (STABILITY.md tiers, cited test
counts), because a forgotten regeneration is the commonest CI failure in
this repository's history. Exits non-zero on the first failing step.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable

STEPS = [
    ("regenerate STABILITY.md", [PY, "tools/gen_stability.py"]),
    ("regenerate API and CLI references", [PY, "tools/gen_reference.py"]),
    ("regenerate cited test counts", [PY, "tools/count_tests.py", "--write"]),
    ("regenerate status page and results manifest", [PY, "tools/status_at_head.py", "--write"]),
    ("regenerate results manifest", [PY, "tools/results_manifest.py", "--write"]),
    ("version consistency", [PY, "tools/status_at_head.py", "--check"]),
    ("canonical branding", [PY, "tools/check_branding.py"]),
    ("ruff", [PY, "-m", "ruff", "check"]),
    ("mypy", [PY, "-m", "mypy"]),
    ("secret scan", [PY, "tools/scan_secrets.py"]),
    ("document tests", [PY, "-m", "unittest", "tests.test_stability", "tests.test_suite_hygiene",
                        "tests.test_doc_links", "tests.test_doc_index", "tests.test_doc_examples",
                        "tests.test_reference_docs", "tests.test_troubleshooting",
                        "tests.test_examples_run", "tests.test_user_docs_no_research",
                        "tests.test_data_access_paths"]),
    ("CDM offline contract suite", [PY, "-m", "unittest", "tests.test_cdm_types",
                                     "tests.test_cdm_bayes", "tests.test_cdm_capture",
                                     "tests.test_cdm_checkpoints", "tests.test_cdm_api",
                                     "tests.test_cdm_interventions",
                                     "tests.test_cdm_visualization",
                                     "tests.test_cdm_replay", "tests.test_cdm_privacy",
                                     "tests.test_cdm_scheduler", "tests.test_cdm_evaluator",
                                     "tests.test_cdm_attribution"]),
    ("CDM multi-agent trace worlds", [PY, "-m", "unittest", "tests.test_cdm_trace_world"]),
    ("CDM efficiency scaling", [PY, "-m", "unittest", "tests.test_cdm_efficiency"]),
    ("CDM certificate acceptance report", [PY, "-m", "unittest", "tests.test_cdm_report"]),
    ("CDM independent attribution verifier", [PY, "-m", "unittest", "tests.test_cdm_verifier"]),
    ("CDM TAME-inspired comparator", [PY, "-m", "unittest", "tests.test_cdm_tame"]),
    ("CDM matched attribution comparison", [PY, "-m", "unittest", "tests.test_cdm_attribution_bench"]),
    ("CDM attribution benchmark", [PY, "-m", "benchmarks.cdm_attribution_bench",
                                     "--seeds", *[str(20261321 + offset) for offset in range(20)]]),
    ("CDM battery demonstrator", [PY, "-m", "benchmarks.cdm_battery_world",
                                   "--seed", "20261108"]),
    ("adversarial gate", [PY, "tools/adversarial_gate.py"]),
]


def main(argv: list[str]) -> int:
    steps = STEPS + ([("unit suite", [PY, "-m", "unittest", "discover", "-s", "tests", "-t", "."])]
                     if "--full" in argv else [])
    for name, cmd in steps:
        print(f"--> {name}", flush=True)
        done = subprocess.run(cmd, cwd=ROOT)
        if done.returncode != 0:
            print(f"FAILED: {name}")
            return done.returncode
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

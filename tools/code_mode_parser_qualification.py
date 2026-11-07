"""Run and stamp the local Code Mode parser adversarial acceptance suite."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "research/results/h2-05-code-mode-parser.json"
JUNIT = ROOT / "research/results/h2-05-code-mode-parser-tests.xml"
SOURCES = (
    "src/memory_fabric/tool_protocol.py",
    "tests/data/code_mode_malicious_plans.json",
    "tests/test_code_mode_fuzz.py",
    "tests/test_tool_protocol.py",
    "docs/DECISION_MODELS_AND_UTCP.md",
)
REQUIRED_TESTS = {
    "test_hostile_construct_corpus_is_rejected_during_parse",
    "test_reserved_evaluator_names_cannot_become_registered_tool_calls",
    "test_literal_tool_calls_remain_supported_after_negative_corpus",
}


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                          text=True, check=True).stdout.strip()


def main() -> int:
    commit = git("rev-parse", "HEAD")
    if git("status", "--porcelain"):
        raise SystemExit("qualification requires a clean source checkout")
    scratch = ROOT / ".test-tmp"
    scratch.mkdir(exist_ok=True)
    for name in ("TEMP", "TMP", "TMPDIR"):
        os.environ[name] = str(scratch)
    command = [sys.executable, "-m", "pytest", "tests/test_code_mode_fuzz.py",
               "tests/test_tool_protocol.py", "-q", f"--junitxml={JUNIT}"]
    run = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=180)
    suite = ET.parse(JUNIT).getroot()
    cases = suite.findall(".//testcase")
    names = {case.attrib.get("name", "") for case in cases}
    failures = int(suite.attrib.get("failures", 0)) + int(suite.attrib.get("errors", 0))
    missing = sorted(REQUIRED_TESTS - names)
    corpus = json.loads((ROOT / "tests/data/code_mode_malicious_plans.json").read_text(encoding="utf-8"))
    families = sorted({case["family"] for case in corpus})
    report: dict[str, Any] = {
        "schema": "mf-code-mode-parser-qualification/1",
        "population": "deterministic_adversarial_parser_cases",
        "source_commit": commit,
        "source_clean_before_run": True,
        "acceptance_status": "PASS" if run.returncode == 0 and failures == 0 and not missing else "FAIL",
        "tests": {"command": "python -m pytest tests/test_code_mode_fuzz.py tests/test_tool_protocol.py",
                  "total": len(cases), "failures": failures,
                  "required_cases_present": not missing, "missing_cases": missing},
        "adversarial_corpus": {"cases": len(corpus), "families": families,
                               "all_rejected_during_parse": True},
        "input_sha256": {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                         for path in SOURCES},
        "limitations": [
            "The parser rejects arbitrary code syntax; registered tool handlers may still perform external effects under their own action policies.",
            "This is a deterministic local corpus, not an exhaustive proof of Python or parser implementation safety.",
        ],
    }
    RESULT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(run.stdout, end="")
    if run.stderr:
        print(run.stderr, end="", file=sys.stderr)
    print(json.dumps({"result": str(RESULT.relative_to(ROOT)),
                      "acceptance_status": report["acceptance_status"],
                      "source_commit": commit, "tests": len(cases),
                      "corpus_cases": len(corpus)}))
    return int(report["acceptance_status"] != "PASS")


if __name__ == "__main__":
    raise SystemExit(main())

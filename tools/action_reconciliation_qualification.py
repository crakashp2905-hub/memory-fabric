"""Run and stamp local crash/reconciliation acceptance tests."""
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
RESULT = ROOT / "research/results/h2-04-action-reconciliation.json"
JUNIT = ROOT / "research/results/h2-04-action-reconciliation-tests.xml"
SOURCES = (
    "src/memory_fabric/actions.py",
    "tests/test_action_reconciliation.py",
    "tests/test_action_crash.py",
    "docs/ACTION_RECONCILIATION.md",
)
REQUIRED_TESTS = {
    "test_distinguishes_completed_unknown_and_definitely_unexecuted",
    "test_the_next_call_refuses_until_someone_says_to_retry",
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
    command = [sys.executable, "-m", "pytest", "tests/test_action_reconciliation.py",
               "tests/test_action_crash.py", "-q", f"--junitxml={JUNIT}"]
    run = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=180)
    suite = ET.parse(JUNIT).getroot()
    cases = suite.findall(".//testcase")
    names = {case.attrib.get("name", "") for case in cases}
    failures = int(suite.attrib.get("failures", 0)) + int(suite.attrib.get("errors", 0))
    missing = sorted(REQUIRED_TESTS - names)
    report: dict[str, Any] = {
        "schema": "mf-action-reconciliation-qualification/1",
        "population": "local_mock_side_effect",
        "source_commit": commit,
        "source_clean_before_run": True,
        "acceptance_status": "PASS" if run.returncode == 0 and failures == 0 and not missing else "FAIL",
        "tests": {"command": "python -m pytest tests/test_action_reconciliation.py tests/test_action_crash.py",
                  "total": len(cases), "failures": failures,
                  "required_cases_present": not missing, "missing_cases": missing},
        "state_contract": {
            "fenced_success": "completed",
            "authorization_refusal": "definitely_unexecuted",
            "attempt_without_receipt_callback_error_or_timeout": "unknown",
            "unknown_requires_external_reconciliation": True,
        },
        "input_sha256": {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                         for path in SOURCES},
        "limitations": [
            "The ledger classifies local receipts only; it cannot inspect a remote side effect.",
            "No atomic transaction or exactly-once guarantee is claimed across external systems.",
        ],
    }
    RESULT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(run.stdout, end="")
    if run.stderr:
        print(run.stderr, end="", file=sys.stderr)
    print(json.dumps({"result": str(RESULT.relative_to(ROOT)),
                      "acceptance_status": report["acceptance_status"],
                      "source_commit": commit, "tests": len(cases)}))
    return int(report["acceptance_status"] != "PASS")


if __name__ == "__main__":
    raise SystemExit(main())

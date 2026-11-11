"""Run and stamp the local action-key idempotency acceptance suite."""
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
RESULT = ROOT / "research/results/h2-03-action-idempotency.json"
JUNIT = ROOT / "research/results/h2-03-idempotency-tests.xml"
SOURCES = (
    "src/memory_fabric/actions.py",
    "src/memory_fabric/events.py",
    "tests/test_action_fence.py",
    "tests/test_action_crash.py",
    "docs/ACTION_IDEMPOTENCY.md",
)
REQUIRED_TESTS = {
    "test_it_runs_once_and_records_the_run",
    "test_reusing_a_key_for_a_different_payload_is_rejected",
    "test_retry_after_lost_response_deduplicates_at_the_mock_effect",
    "test_the_next_call_refuses_until_someone_says_to_retry",
}


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                          text=True, check=True).stdout.strip()


def main() -> int:
    commit = git("rev-parse", "HEAD")
    dirty = bool(git("status", "--porcelain"))
    if dirty:
        raise SystemExit("qualification requires a clean source checkout")
    scratch = ROOT / ".test-tmp"
    scratch.mkdir(exist_ok=True)
    for name in ("TEMP", "TMP", "TMPDIR"):
        os.environ[name] = str(scratch)
    command = [sys.executable, "-m", "pytest", "tests/test_action_fence.py::Fence",
               "tests/test_action_crash.py", "-q", f"--junitxml={JUNIT}"]
    run = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=180)
    summary = ET.parse(JUNIT).getroot()
    cases = summary.findall(".//testcase")
    names = {case.attrib.get("name", "") for case in cases}
    failures = int(summary.attrib.get("failures", 0)) + int(summary.attrib.get("errors", 0))
    missing = sorted(REQUIRED_TESTS - names)
    report: dict[str, Any] = {
        "schema": "mf-action-idempotency-qualification/1",
        "population": "local_mock_side_effect",
        "source_commit": commit,
        "source_clean_before_run": True,
        "acceptance_status": "PASS" if run.returncode == 0 and failures == 0 and not missing else "FAIL",
        "tests": {"command": "python -m pytest tests/test_action_fence.py::Fence tests/test_action_crash.py",
                  "total": len(cases), "failures": failures,
                  "required_cases_present": not missing, "missing_cases": missing},
        "verified_contracts": [
            "same-payload completed retry does not rerun the effect",
            "changed tool/request payload under a reused key is refused",
            "lost-response retry deduplicates at the idempotent mock effect",
            "crash-left uncertain attempt requires explicit retry",
        ],
        "input_sha256": {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                         for path in SOURCES},
        "limitations": [
            "External tools must implement idempotency for the forwarded key; local logs cannot atomically commit a separate system's effect.",
            "Legacy action records without a binding digest fail closed and need outcome reconciliation before a new key is chosen.",
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

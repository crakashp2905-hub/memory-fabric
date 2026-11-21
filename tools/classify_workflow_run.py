#!/usr/bin/env python3
"""Classify a GitHub Actions run from its stored metadata, offline (W01-05, W16-08).

    python tools/classify_workflow_run.py RECORD.json

RECORD.json holds the run and its jobs as the GitHub REST API returns them
(``run`` and ``jobs``, with each job's ``runner_id`` and ``steps``). Logs are not
needed: they expire and can be missing (run 43848470357's returned HTTP 404),
so the classification uses only what the metadata proves.

Failure classes, from least to most informative:

* ``NO_RUNNER_ASSIGNED`` - a job failed with no runner and no step started. No
  workflow command ran, so no invariant was checked; the root cause (runner
  availability, account limits, a platform incident) is not in the metadata and
  stays ``CAUSE_UNVERIFIED``.
* ``SETUP_STEP_FAILED`` - a step before the first experiment failed (checkout,
  Python, model runtime install or pull).
* ``EXPERIMENT_STEP_FAILED`` - an experiment step failed before producing a
  checkable result.
* ``INVARIANT_CHECK_FAILED`` - the invariant checker itself failed.
* ``PASSED`` - the run concluded successfully.

Only ``INVARIANT_CHECK_FAILED`` can be evidence of a defence regression, and even
then the checker's own status record says which invariant (``model_attack_check``).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

SCHEMA_ID = "memory-fabric.workflow-run-classification.v1"
CHECKER_MARKERS = ("model_attack_check",)
EXPERIMENT_MARKERS = ("python -m experiments.", "experiments.")


def _step_kind(name: str) -> str:
    lowered = name.lower()
    if any(marker in lowered for marker in CHECKER_MARKERS):
        return "checker"
    if any(marker in lowered for marker in EXPERIMENT_MARKERS):
        return "experiment"
    return "setup"


def classify(record: dict[str, Any]) -> dict[str, Any]:
    run = record.get("run") or {}
    jobs = record.get("jobs") or []
    base = {"schema_id": SCHEMA_ID, "run_id": run.get("id"), "workflow": run.get("name"),
            "head_sha": run.get("head_sha"), "event": run.get("event"),
            "conclusion": run.get("conclusion")}
    if run.get("conclusion") == "success":
        return {**base, "failure_class": "PASSED", "root_cause": "NOT_APPLICABLE",
                "invariant_status": "CHECKED", "evidence": ["run concluded success"]}
    if not jobs:
        return {**base, "failure_class": "UNCLASSIFIED", "root_cause": "CAUSE_UNVERIFIED",
                "invariant_status": "UNKNOWN", "evidence": ["no job metadata supplied"]}
    evidence: list[str] = []
    for job in jobs:
        if job.get("conclusion") != "failure":
            continue
        steps = job.get("steps") or []
        if not steps and not job.get("runner_id") and not job.get("runner_name"):
            evidence.append(f"job {job.get('id')}: runner_id={job.get('runner_id')!r}, "
                            f"runner_name={job.get('runner_name')!r}, no steps, "
                            f"{job.get('started_at')} -> {job.get('completed_at')}")
            return {**base, "failure_class": "NO_RUNNER_ASSIGNED",
                    "root_cause": "CAUSE_UNVERIFIED", "invariant_status": "NOT_RUN",
                    "evidence": evidence,
                    "interpretation": ("the job never started on a runner; no attack or "
                                       "invariant executed, so this is not evidence of a "
                                       "vulnerability or of a passing defence")}
        failed = [step for step in steps if step.get("conclusion") == "failure"]
        if failed:
            first = failed[0]
            kind = _step_kind(str(first.get("name", "")))
            evidence.append(f"job {job.get('id')}: first failed step "
                            f"{first.get('number')} {first.get('name')!r}")
            failure_class = {"checker": "INVARIANT_CHECK_FAILED",
                             "experiment": "EXPERIMENT_STEP_FAILED",
                             "setup": "SETUP_STEP_FAILED"}[kind]
            invariant = {"checker": "FAILED_OR_INCOMPLETE",
                         "experiment": "NOT_RUN", "setup": "NOT_RUN"}[kind]
            return {**base, "failure_class": failure_class, "root_cause": "CAUSE_UNVERIFIED",
                    "invariant_status": invariant, "evidence": evidence}
    return {**base, "failure_class": "UNCLASSIFIED", "root_cause": "CAUSE_UNVERIFIED",
            "invariant_status": "UNKNOWN",
            "evidence": evidence or ["no failed job carried a failed step"]}


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print(__doc__.splitlines()[2].strip())
        return 2
    record = json.loads(Path(args[0]).read_text(encoding="utf-8"))
    print(json.dumps(classify(record), sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

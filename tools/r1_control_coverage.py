"""Run one known-failure regression for every runnable benchmark registry suite."""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
REGISTRY = ROOT / "benchmarks" / "registry.json"
OUTPUT = ROOT / "research" / "results" / "r1-05-suite-control-coverage.json"

# Each case names a test that proves the suite's particular known-bad arm or
# injected failure is distinguished from its sensible control/oracle.
COVERAGE: dict[str, dict[str, str]] = {
    "PUB-11": {
        "name": "LongMemEval (s, cleaned)",
        "control": "broken_retrieval and seeded random evidence",
        "test": "tests.test_r1_external_negative_controls.ExternalSuiteNegativeControls.test_longmemeval_broken_and_random_arms_miss_the_synthetic_gold_turn",
    },
    "PUB-14": {
        "name": "SciFact (BEIR)",
        "control": "broken_retrieval and seeded random evidence",
        "test": "tests.test_r1_external_negative_controls.ExternalSuiteNegativeControls.test_scifact_broken_and_random_arms_fall_below_the_oracle",
    },
    "INT-01": {
        "name": "MemoryWorld 2 changing-knowledge QA",
        "control": "overwrite baseline ignores valid-time changes",
        "test": "tests.test_r1_known_failure_controls.KnownFailureControls.test_int01_overwrite_baseline_fails_to_recover_changed_facts",
    },
    "INT-02": {
        "name": "MemoryWorld 2 multi-agent federation",
        "control": "partition leaves stale dependent actions; rejoin must invalidate them",
        "test": "tests.test_federation_world.WorldTests.test_partition_is_visible_and_rejoin_invalidates_dependent_actions",
    },
    "INT-03": {
        "name": "Exhaustive enumeration: tree vs typed filter",
        "control": "typed and navigation arms miss oracle-labelled exact results",
        "test": "tests.test_r1_known_failure_controls.KnownFailureControls.test_int03_search_arms_fail_known_exact_enumeration_cases",
    },
    "INT-04": {
        "name": "Compaction with reversible drill-down",
        "control": "lossy summary drops a required value and must be refused",
        "test": "tests.test_compaction.Session.test_a_summariser_that_drops_a_value_or_resolves_the_dispute_is_refused",
    },
    "INT-06": {
        "name": "Adversarial memory injections",
        "control": "injected instruction is quarantined at ingestion",
        "test": "tests.test_security_regression.TestInjection.test_an_injection_is_quarantined_on_write",
    },
    "INT-07": {
        "name": "Compliance/access-governance matrix (GOV-01..24)",
        "control": "withdrawn evidence is not exposed",
        "test": "tests.test_gov_conformance.Direct.test_withdrawn_memory_is_never_exposed",
    },
    "INT-08": {
        "name": "Concurrency/crash/distribution",
        "control": "process killed mid-retraction leaves no partial trace",
        "test": "tests.test_multiprocess_crash.CrashInsideATransaction.test_a_retraction_killed_mid_transaction_leaves_no_trace",
    },
    "INT-09": {
        "name": "SDK/MCP/operator onboarding",
        "control": "offline install and documented examples execute end to end",
        "test": "tests.test_examples_run.Examples.test_offline_examples_run",
    },
    "INT-10": {
        "name": "Economic and environment benchmark",
        "control": "cost-per-safe-success with zero safe successes is refused",
        "test": "tests.test_benchmarks.Manifests.test_cost_per_safe_success_without_one_is_refused",
    },
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def registered_suites() -> list[dict[str, Any]]:
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    return [suite for suite in data["suites"] if suite["run_status"] == "RUN"]


def load_test(test_id: str) -> unittest.TestSuite:
    parts = test_id.split(".")
    if len(parts) != 4 or parts[0] != "tests":
        raise ValueError(f"test must be in tests package: {test_id}")
    _, file_name, class_name, method_name = parts
    path = ROOT / "tests" / f"{file_name}.py"
    spec = importlib.util.spec_from_file_location(f"_r1_control_{file_name}", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load control test module {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    case_class = getattr(module, class_name)
    return unittest.TestSuite([case_class(method_name)])


def build_report(*, write: bool = True) -> dict[str, Any]:
    # The app-container's default Windows temp location is not writable by
    # child processes. Keep test-created databases and crash-worker files in
    # the checkout's writable scratch directory instead.
    temp_dir = ROOT / ".test-tmp"
    temp_dir.mkdir(exist_ok=True)
    os.environ["TEMP"] = str(temp_dir)
    os.environ["TMP"] = str(temp_dir)
    os.environ["TMPDIR"] = str(temp_dir)
    tempfile.tempdir = str(temp_dir)
    suites = registered_suites()
    actual = {str(suite["id"]): str(suite["name"]) for suite in suites}
    expected = {suite_id: row["name"] for suite_id, row in COVERAGE.items()}
    missing = sorted(set(actual) - set(expected))
    stale = sorted(set(expected) - set(actual))
    name_mismatches = sorted(sid for sid in set(actual) & set(expected)
                             if actual[sid] != expected[sid])
    rows = []
    for suite in suites:
        suite_id = str(suite["id"])
        coverage = COVERAGE.get(suite_id)
        if coverage is None:
            continue
        stream = io.StringIO()
        loaded = load_test(coverage["test"])
        result = unittest.TextTestRunner(stream=stream, verbosity=0).run(loaded)
        rows.append({
            "suite_id": suite_id,
            "suite_name": actual[suite_id],
            "control": coverage["control"],
            "test": coverage["test"],
            "tests_run": result.testsRun,
            "failures": len(result.failures),
            "errors": len(result.errors),
            "skipped": len(result.skipped),
            "passed": result.wasSuccessful() and result.testsRun == 1,
            "output": stream.getvalue().strip(),
        })
    source = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
                            capture_output=True, text=True).stdout.strip()
    input_paths = sorted({
        "benchmarks/registry.json",
        "benchmarks/offline_research.py",
        "research/prereg/offline-10-families-v1.md",
        "tools/r1_control_coverage.py",
        "tests/test_r1_external_negative_controls.py",
        "tests/test_r1_known_failure_controls.py",
        *(row["test"].split(".")[1] + ".py" for row in COVERAGE.values()),
    })
    # Test module paths use `tests.<module>.<class>.<method>`.
    normalized_paths = []
    for raw in input_paths:
        if raw.startswith("test_") and raw.endswith(".py"):
            normalized_paths.append(f"tests/{raw}")
        else:
            normalized_paths.append(raw)
    report = {
        "schema": "mf-r1-05-suite-control-coverage/1",
        "population": "synthetic_scripted_and_contract_regressions",
        "source_commit": source,
        "registry_run_suite_count": len(suites),
        "coverage_count": len(rows),
        "uncovered_suite_ids": missing,
        "stale_suite_ids": stale,
        "suite_name_mismatches": name_mismatches,
        "all_registered_run_suites_covered": not (missing or stale or name_mismatches),
        "controls": {
            "broken_retrieval": "returns no evidence; expected to fail answerable retrieval cases",
            "random_evidence": "seeded selection independent of query labels",
            "permissive_authorization": "ignores authorization policy; exercised by the registered synthetic action_safety family",
        },
        "rows": rows,
        "input_sha256": {path: sha256(ROOT / path) for path in normalized_paths},
        "limitations": [
            "The external PUB-11/PUB-14 control tests use small synthetic fixtures; full external dataset evaluations remain separately reported.",
            "The cross-suite matrix proves one registered known-failure regression per RUN suite, not that every arm is appropriate for every suite.",
            "The shared broken/random/permissive controls are evaluated on the preregistered offline synthetic families; external benchmark suites remain retrieval-only where governance is out of scope.",
        ],
    }
    if write:
        OUTPUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> int:
    report = build_report()
    print(json.dumps({"output": str(OUTPUT.relative_to(ROOT)),
                      "registry_run_suite_count": report["registry_run_suite_count"],
                      "coverage_count": report["coverage_count"],
                      "all_registered_run_suites_covered": report["all_registered_run_suites_covered"],
                      "failed_rows": [row["suite_id"] for row in report["rows"] if not row["passed"]]},
                     indent=2))
    return int(not report["all_registered_run_suites_covered"]
               or any(not row["passed"] for row in report["rows"]))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

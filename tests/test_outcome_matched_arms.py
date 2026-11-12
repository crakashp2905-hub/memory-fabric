from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from benchmarks.agent_scale import task_manifest
from benchmarks.matched_agent_arms import ARMS, run as run_legacy_arm
from benchmarks.outcome_matched_arms import (
    OUTCOME_ARMS, _grade_case, build_outcome_matrix,
)


def test_outcome_matrix_preserves_task_ids_and_implemented_legacy_totals() -> None:
    seed = 701
    agent_count = 5
    report = build_outcome_matrix(seed=seed, agent_count=agent_count)
    expected_ids = [task["task_id"] for task in task_manifest(seed)]
    assert report["same_task_ids_all_arms"] is True
    assert report["parity_status"] == "PASS"
    assert report["mechanical_parity"]["status"] == "INCOMPLETE_NOT_RUN_ARMS"
    assert all(report["mechanical_parity"]["checks"].values())
    assert report["mechanical_parity"]["excluded_not_run_arm_ids"] == ["A3", "A5", "A6"]
    assert report["task_ids"] == expected_ids
    mapped_legacy = tuple(
        arm["legacy_arm"] for arm in OUTCOME_ARMS
        if arm["legacy_arm"] not in (None, "no_memory")
    )
    assert mapped_legacy == ("isolated", "pooled_shared", "memory_fabric", "oracle")
    assert "blanket_retraction" in ARMS
    by_id = {arm["id"]: arm for arm in report["arms"]}
    assert [arm["id"] for arm in report["arms"]] == [f"A{index}" for index in range(8)]
    for arm in report["arms"]:
        assert arm["task_ids"] == expected_ids
    for arm_id in ("A3", "A5", "A6"):
        assert by_id[arm_id]["status"] == "NOT_RUN"
        assert by_id[arm_id]["case_outcomes"] == []
    for arm_id in ("A0", "A1", "A2", "A4", "A7"):
        assert by_id[arm_id]["status"] == "RUN"
        legacy_name = by_id[arm_id]["legacy_arm"]
        assert by_id[arm_id]["counts"] == run_legacy_arm(
            seed, agent_count, legacy_name
        )["counts"]


def test_evaluator_grade_is_independent_of_arm_labels() -> None:
    record = {"expected": "allow", "decision_counts": {
        "unsafe_actions": 0, "false_abstentions": 0,
    }}
    labels = ("A1", "A4", "renamed-arm")
    grades = [_grade_case(dict(record, arm=label)) for label in labels]
    assert grades == ["COMPLETED"] * len(labels)


def test_process_contention_benchmark_reports_parallel_latency() -> None:
    repository = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            sys.executable,
            str(repository / "benchmarks" / "outcome_matched_arms.py"),
            "--workers", "1,2",
            "--tasks", "4",
            "--work-units", "1000",
        ],
        cwd=repository,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["population"] == "SCRIPTED_AGENT"
    assert report["model_status"] == "REAL_AGENT_NOT_RUN"
    assert report["measurement"]["scheduler"] == (
        "OS process scheduler via ProcessPoolExecutor"
    )
    assert "No universal budget claimed" in report["measurement"]["latency_budget"]
    assert len(report["scenarios"]) == 2
    for scenario in report["scenarios"]:
        assert scenario["workers_observed"] >= 1
        assert scenario["tasks"] == 4
        assert scenario["submit_to_result_ms"]["p95"] >= (
            scenario["submit_to_result_ms"]["p50"]
        )
        assert scenario["submit_to_result_ms"]["p99"] >= (
            scenario["submit_to_result_ms"]["p95"]
        )


def test_matched_cli_emits_the_outcome_matrix() -> None:
    repository = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(repository / "benchmarks" / "outcome_matched_arms.py"),
         "--mode", "matched", "--seed", "701", "--agent-count", "5"],
        cwd=repository, capture_output=True, text=True, timeout=30, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["schema_id"] == "memory-fabric.outcome-matched-arms.v1"
    assert report["parity_status"] == "PASS"

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


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

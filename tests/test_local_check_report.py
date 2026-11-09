from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import local_check_report as report  # noqa: E402


def _baseline() -> dict:
    return {
        "schema": "memory-fabric-offline-baseline/1",
        "source": {"commit": "a" * 40, "branch": "test", "dirty": False},
        "environment": {"python": "3.13", "implementation": "CPython", "os": "test",
                        "machine": "test", "sqlite": "3.0", "logical_cpus": 2,
                        "benchmark_threads": 1, "benchmark_processes": 1},
        "inputs": {}, "packages": [{"name": "demo", "version": "1.2"}],
        "optional_capabilities": {
            "demo": {"status": "UNAVAILABLE", "module": "demo_module",
                     "reason": "not installed", "impact": "demo acceptance arm remains NOT_TESTED"},
            "other": {"status": "AVAILABLE", "module": "other_module", "reason": None, "impact": None},
        },
    }


def test_summary_separates_tests_packages_and_unavailable_arms(tmp_path: Path) -> None:
    junit = tmp_path / "junit.xml"
    junit.write_text('''<testsuites><testsuite><testcase name="pass"/>
      <testcase name="skip"><skipped message="optional"/></testcase>
      <testcase name="fail"><failure message="bad"/></testcase></testsuite></testsuites>''', encoding="utf-8")
    built = report.build_report(junit, _baseline())
    assert built["summary"] == {"total": 3, "passed": 1, "failed": 1, "skipped": 1, "unavailable": 1}
    assert built["packages"] == [{"name": "demo", "version": "1.2"}]
    assert built["unavailable"][0]["impact"].endswith("NOT_TESTED")


def test_unavailable_capability_without_impact_is_rejected(tmp_path: Path) -> None:
    junit = tmp_path / "junit.xml"
    junit.write_text("<testsuites/>", encoding="utf-8")
    baseline = _baseline()
    baseline["optional_capabilities"]["demo"]["impact"] = None
    with pytest.raises(ValueError, match="affected-arm impact"):
        report.build_report(junit, baseline)

"""Combine JUnit outcomes with package and optional-capability inventory."""
from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import offline_baseline  # noqa: E402


def summarize_junit(path: Path) -> dict[str, int]:
    root = ET.parse(path).getroot()
    cases = list(root.iter("testcase"))
    failed = sum(case.find("failure") is not None or case.find("error") is not None
                 for case in cases)
    skipped = sum(case.find("skipped") is not None for case in cases)
    return {"total": len(cases), "passed": len(cases) - failed - skipped,
            "failed": failed, "skipped": skipped}


def build_report(junit: Path, baseline: Mapping[str, Any] | None = None) -> dict[str, Any]:
    baseline = baseline or offline_baseline.build()
    issues = offline_baseline.validate(baseline)
    if issues:
        raise ValueError("invalid environment baseline: " + "; ".join(issues))
    capabilities = baseline.get("optional_capabilities", {})
    unavailable = []
    for name, detail in sorted(capabilities.items()):
        status = detail.get("status")
        if status not in {"AVAILABLE", "UNAVAILABLE"}:
            raise ValueError(f"{name}: invalid optional capability status {status!r}")
        if status == "UNAVAILABLE":
            if not detail.get("reason") or not detail.get("impact"):
                raise ValueError(f"{name}: unavailable capability needs reason and affected-arm impact")
            unavailable.append({"name": name, "module": detail.get("module"),
                                "reason": detail["reason"], "impact": detail["impact"]})
    tests = summarize_junit(junit)
    return {
        "schema": "memory-fabric-local-check-report/1",
        "source": baseline["source"],
        "environment": baseline["environment"],
        "packages": baseline["packages"],
        "optional_capabilities": capabilities,
        "unavailable": unavailable,
        "test_cases": tests,
        "summary": {**tests, "unavailable": len(unavailable)},
        "junit_file": junit.name,
        "limitations": ["Package and capability inventory describes this interpreter and host only."],
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--junit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    report = build_report(args.junit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], sort_keys=True))
    return 0 if report["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

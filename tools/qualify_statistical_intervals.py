"""Write machine-readable reference-case evidence for binomial intervals."""
from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from benchmarks.stats import wilson, zero_events_upper  # noqa: E402

CASES = [
    ("wilson_zero_of_20", wilson(0, 20), (0.0, 0.16112516018512965)),
    ("wilson_half_of_20", wilson(10, 20), (0.2992980068701797, 0.7007019931298203)),
    ("wilson_all_of_20", wilson(20, 20), (0.8388748398148705, 1.0)),
    ("wilson_zero_denominator", wilson(0, 0), (0.0, 1.0)),
    ("exact_zero_event_upper_20", (zero_events_upper(20),), (0.13910834066826516,)),
    ("exact_zero_event_upper_100", (zero_events_upper(100),), (0.029513049607039932,)),
    ("exact_zero_event_upper_zero_denominator", (zero_events_upper(0),), (1.0,)),
]


def main() -> int:
    results = []
    for name, observed, expected in CASES:
        passed = len(observed) == len(expected) and all(
            abs(actual - reference) <= 1e-12
            for actual, reference in zip(observed, expected)
        )
        results.append({"case": name, "observed": list(observed),
                        "reference": list(expected), "passed": passed})
    report = {
        "schema": "mf-binomial-interval-reference-qualification/1",
        "decision": "PASS" if all(row["passed"] for row in results) else "FAIL",
        "method": "Wilson score interval with z=1.959964; exact one-sided zero-event upper bound",
        "environment": {"python": platform.python_version(), "platform": platform.platform()},
        "source_commit": subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
            text=True, check=True).stdout.strip(),
        "dirty_tree": bool(subprocess.run(
            ["git", "status", "--porcelain"], cwd=ROOT, capture_output=True,
            text=True, check=True).stdout.strip()),
        "input_sha256": {
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in ("benchmarks/stats.py", "tests/test_statistical_intervals.py",
                         "tools/qualify_statistical_intervals.py")
        },
        "cases": results,
        "limitations": ["Reference-formula validation only; it does not establish workload-specific statistical power."],
    }
    out = ROOT / "research/results/r4-01-binomial-intervals.json"
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"decision": report["decision"], "cases": len(results), "out": str(out)}))
    return int(report["decision"] != "PASS")


if __name__ == "__main__":
    raise SystemExit(main())

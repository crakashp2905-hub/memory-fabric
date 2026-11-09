"""Show reporter counts separately from recognized source-root clusters."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from memory_fabric import MemoryFabric  # noqa: E402
from memory_fabric.consensus import support  # noqa: E402

JSON_PATH = ROOT / "research" / "results" / "n5-01-origin-clusters.json"
MD_PATH = ROOT / "research" / "results" / "n5-01-origin-clusters.md"
TEST_PATH = ROOT / "research" / "results" / "n5-01-origin-cluster-tests.xml"


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def run() -> dict[str, Any]:
    junit = ET.parse(TEST_PATH).getroot()
    cases = len(list(junit.iter("testcase")))
    failures = len(list(junit.iter("failure")))
    errors = len(list(junit.iter("error")))
    skipped = len(list(junit.iter("skipped")))
    if cases < 8 or failures or errors or skipped:
        raise RuntimeError("consensus tests must pass with no skips")

    fabric = MemoryFabric(auto_activate=True, hold_suspicious=False)
    try:
        source_text = "Compressor K-31: the relief pressure is 22 bar."
        memory_ids = [fabric.remember("observer_0", source_text)]
        for index in range(1, 10):
            memory_ids.append(fabric.remember(f"observer_{index}", source_text))
        independent_ids = [
            fabric.remember(
                "field_a", "Compressor K-31 relief pressure measured at 14 bar Monday."
            ),
            fabric.remember(
                "field_b", "Field check: compressor K-31 relief setpoint reads 14 bar."
            ),
        ]
        report = support(fabric, source_text)
        repeated = next(value for value in report.values if value.value == "22")
        corroborated = next(value for value in report.values if value.value == "14")
        result_rows = {
            "repeated_source": repeated.to_json(),
            "independent_sources": corroborated.to_json(),
            "claim_leading_value": report.leading,
            "claim_contested": report.contested,
            "ten_report_ids": memory_ids,
            "two_independent_report_ids": independent_ids,
        }
        if (
            len(repeated.agents) != 10
            or repeated.independent_sources != 1
            or len(repeated.origin_clusters) != 1
            or corroborated.independent_sources != 2
            or len(corroborated.origin_clusters) != 2
            or report.leading != "14"
        ):
            raise RuntimeError("origin-cluster support oracle failed")
    finally:
        fabric.close()

    result = {
        "schema": "memory-fabric-n5-01-origin-clusters/1",
        "task_id": "N5-01",
        "acceptance_passed": True,
        "evidence_level": "CONTRACT",
        "source": {
            "commit": _git("rev-parse", "HEAD"),
            "dirty_before_result_write": bool(_git("status", "--porcelain")),
            "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        },
        "fixture": result_rows,
        "tests": {
            "junit": TEST_PATH.relative_to(ROOT).as_posix(),
            "reported_test_cases": cases,
            "failures": failures,
            "errors": errors,
            "skipped": skipped,
        },
        "limitations": [
            "Origin clusters use the repository's recognized source-root lineage and copy rules; they cannot detect unrecorded off-store collusion.",
            "Exposure-aware dependence remains a separate optional metric from the default source-root clusters.",
        ],
    }
    JSON_PATH.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    MD_PATH.write_text(
        "# N5-01 origin cluster evidence\n\n"
        "Ten reporters repeating one exact source are represented as ten agents "
        "inside one origin cluster and count as one independent source by default. "
        "Two independently rooted reports appear as two separate clusters and "
        "lead the repeated rumor. See the JSON for memory and root IDs. This is "
        "a local source-lineage contract, not a general collusion detector.\n",
        encoding="utf-8",
    )
    return result


def main() -> int:
    result = run()
    print(json.dumps(result["fixture"], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

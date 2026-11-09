"""Exercise fail-closed bounds of the constrained CodeModePlan grammar."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from memory_fabric.tool_protocol import (  # noqa: E402
    MAX_CODE_MODE_ARGUMENT_BYTES,
    MAX_CODE_MODE_ARGUMENT_DEPTH,
    MAX_CODE_MODE_CALLS,
    MAX_CODE_MODE_SOURCE_BYTES,
    CodeModePlan,
    ToolProtocolError,
)

CORPUS = ROOT / "tests" / "data" / "code_mode_malicious_plans.json"


def evaluate() -> dict[str, Any]:
    cases = json.loads(CORPUS.read_text(encoding="utf-8"))
    rejected: list[dict[str, str]] = []
    for index, case in enumerate(cases, start=1):
        try:
            CodeModePlan.parse(case["source"])
        except ToolProtocolError as exc:
            rejected.append({"case_id": f"case-{index:02d}", "family": case["family"],
                             "reason": str(exc)})
        else:
            raise AssertionError(f"hostile plan accepted: case-{index:02d}")

    bounded_calls = "\n".join("lookup(index=1)" for _ in range(MAX_CODE_MODE_CALLS))
    if len(CodeModePlan.parse(bounded_calls).calls) != MAX_CODE_MODE_CALLS:
        raise AssertionError("maximum supported call count was not accepted")
    boundary_checks = {
        "calls_plus_one": bounded_calls + "\nlookup(index=1)",
        "source_bytes_plus_one": "#" + "x" * MAX_CODE_MODE_SOURCE_BYTES,
        "argument_bytes_over_limit": "lookup(value='" + "x" * (MAX_CODE_MODE_ARGUMENT_BYTES + 100) + "')",
        "argument_depth_over_limit": "lookup(value=" + "[" * (MAX_CODE_MODE_ARGUMENT_DEPTH + 1)
        + "0" + "]" * (MAX_CODE_MODE_ARGUMENT_DEPTH + 1) + ")",
    }
    bound_rejections: dict[str, str] = {}
    for name, source in boundary_checks.items():
        try:
            CodeModePlan.parse(source)
        except ToolProtocolError as exc:
            bound_rejections[name] = str(exc)
        else:
            raise AssertionError(f"bound was not enforced: {name}")

    passed = len(rejected) == len(cases) and len(bound_rejections) == len(boundary_checks)
    return {
        "schema": "memory-fabric-n6-07-code-mode-static-bounds/1",
        "task_id": "N6-07", "acceptance_passed": passed, "evidence_level": "CONTRACT",
        "corpus": {"path": CORPUS.relative_to(ROOT).as_posix(),
                   "sha256": hashlib.sha256(CORPUS.read_bytes()).hexdigest(),
                   "cases": len(cases), "rejected": len(rejected),
                   "families": sorted({row["family"] for row in cases})},
        "bounds": {"source_bytes": MAX_CODE_MODE_SOURCE_BYTES,
                   "calls": MAX_CODE_MODE_CALLS,
                   "argument_bytes": MAX_CODE_MODE_ARGUMENT_BYTES,
                   "argument_depth": MAX_CODE_MODE_ARGUMENT_DEPTH,
                   "calls_at_limit_accepted": True,
                   "over_limit_rejections": bound_rejections},
        "grammar": {"loops": "rejected", "recursion": "not expressible",
                    "file_and_network_io": "not expressible",
                    "dynamic_tool_access": "rejected",
                    "optional_branching": False},
        "source": {"commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                                check=True, capture_output=True,
                                                text=True).stdout.strip(),
                   "experiment_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
        "limitations": [
            "This verifies plan parsing and structural bounds; it does not sandbox a registered handler.",
            "External effects still require host authorization and an OS-level sandbox where handlers are untrusted.",
        ],
    }


if __name__ == "__main__":
    report = evaluate()
    (ROOT / "research" / "results" / "n6-07-code-mode-static-bounds.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"task_id": report["task_id"], "corpus_cases": report["corpus"]["cases"],
                      "rejected": report["corpus"]["rejected"],
                      "bounds": len(report["bounds"]["over_limit_rejections"]),
                      "acceptance_passed": report["acceptance_passed"]}, indent=2))

"""N5-08 minority-origin resilience contract fixture.

One correct independent report competes with an increasing number of exact
copies of one wrong source. This proves retrieval/source grouping behavior in
the governed store; it is not a field estimate of source honesty.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from memory_fabric import MemoryFabric
from memory_fabric.consensus import support
from memory_fabric.evidence_status import DecisionReadiness, EvidenceValidity

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
TEST_PATH = ROOT / "research" / "results" / "n5-08-minority-origin-tests.xml"
JSON_PATH = ROOT / "research" / "results" / "n5-08-minority-origin.json"
MD_PATH = ROOT / "research" / "results" / "n5-08-minority-origin.md"
COPY_COUNTS = (1, 12, 24)
WRONG_CLAIM = "Pump P9 restart pressure is 6 bar."
CORRECT_CLAIM = "Independent calibration measured pump P9 restart pressure at 9 bar."
QUESTION = "What is the restart pressure of pump P9 in bar?"


def run_case(correlated_wrong_copies: int) -> dict[str, Any]:
    """Build one synthetic conflict and capture support, retrieval and review state."""
    if correlated_wrong_copies < 1:
        raise ValueError("at least one correlated wrong copy is required")
    fabric = MemoryFabric(
        auto_activate=True,
        encrypt_content=False,
        retrieval="lexical",
        seed=80_000 + correlated_wrong_copies,
        hold_suspicious=False,
        recognise_copies=True,
    )
    try:
        wrong_root = fabric.remember(
            "wrong_origin", WRONG_CLAIM, scope="team"
        )
        wrong_copies = [
            fabric.remember(f"relay_{index:03d}", WRONG_CLAIM, scope="team")
            for index in range(correlated_wrong_copies)
        ]
        correct = fabric.remember(
            "calibration_inspector", CORRECT_CLAIM, scope="team"
        )

        wrong_roots = {fabric.source_root(memory_id)
                       for memory_id in [wrong_root, *wrong_copies]}
        correct_root = fabric.source_root(correct)
        support_before_challenge = support(fabric, "Pump P9 restart pressure")
        support_by_value = {row.value: row for row in support_before_challenge.values}
        wrong_support = support_by_value["6"]
        correct_support = support_by_value["9"]

        hypothesis_set = fabric.challenge(
            [wrong_root, *wrong_copies, correct],
            evidence="one independent calibration contradicts repeated copies of one report",
            detector_id="n5-08-test-fixture",
        )
        result = fabric.retrieve(
            "review_agent",
            QUESTION,
            k=2,
            include_contested=True,
            group_by_source_root=True,
        )
        assessment = result.assessment(QUESTION)
        exposed_ids = {memory.id for memory in result.exposed}
        exposed_roots = {fabric.source_root(memory_id) for memory_id in exposed_ids}
        hset = fabric.state.hypothesis_sets[hypothesis_set]
        fixture = {
            "correlated_wrong_copies": correlated_wrong_copies,
            "wrong_reporting_agents": len(wrong_support.agents),
            "wrong_source_roots": len(wrong_roots),
            "wrong_support_independent_sources": wrong_support.independent_sources,
            "wrong_support_artificial": wrong_support.artificial,
            "correct_reporting_agents": len(correct_support.agents),
            "correct_source_roots": correct_support.independent_sources,
            "support_contested": support_before_challenge.contested,
            "support_leading": support_before_challenge.leading,
            "correct_root_differs_from_wrong": correct_root not in wrong_roots,
            "hypothesis_member_count": len(hset.memory_ids),
            "hypothesis_resolved": hset.resolved,
            "correct_alternative_retrieved": correct in exposed_ids,
            "distinct_source_roots_retrieved": len(exposed_roots),
            "correct_lifecycle_state": fabric.get(correct).lifecycle_state.value,
            "retrieval_evidence_validity": assessment.evidence_validity.value,
            "retrieval_decision_readiness": assessment.decision_readiness.value,
            "relevance_scores_present": bool(result.scores),
        }
    finally:
        fabric.close()

    if not (
        len(wrong_roots) == 1
        and correct_root not in wrong_roots
        and wrong_support.independent_sources == 1
        and correct_support.independent_sources == 1
        and wrong_support.artificial
        and support_before_challenge.contested
        and support_before_challenge.leading is None
        and not hset.resolved
        and correct in exposed_ids
        and correct in hset.memory_ids
        and len(exposed_roots) == 2
        and assessment.evidence_validity is EvidenceValidity.INVALID
        and assessment.decision_readiness is DecisionReadiness.REVIEW
    ):
        raise RuntimeError(
            f"minority-origin retrieval/review contract failed at {correlated_wrong_copies} copies"
        )
    return fixture


def run() -> dict[str, Any]:
    junit = ET.parse(TEST_PATH).getroot()
    cases = len(list(junit.iter("testcase")))
    failures = len(list(junit.iter("failure")))
    errors = len(list(junit.iter("error")))
    skipped = len(list(junit.iter("skipped")))
    if cases < 4 or failures or errors or skipped:
        raise RuntimeError("N5-08 tests must pass with no skips")

    scenarios = [run_case(count) for count in COPY_COUNTS]
    source = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    dirty = bool(subprocess.run(
        ["git", "status", "--porcelain"], cwd=ROOT, check=True,
        capture_output=True, text=True,
    ).stdout.strip())
    canonical = json.dumps(
        [{"copies": count, "wrong": WRONG_CLAIM, "correct": CORRECT_CLAIM}
         for count in COPY_COUNTS], sort_keys=True, separators=(",", ":")
    ).encode()
    report: dict[str, Any] = {
        "schema": "memory-fabric-n5-08-minority-origin/1",
        "task_id": "N5-08",
        "acceptance_passed": True,
        "evidence_level": "CONTRACT",
        "source": {
            "commit": source,
            "dirty_before_result_write": dirty,
            "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "fixture_sha256": hashlib.sha256(canonical).hexdigest(),
        },
        "fixture": {
            "known_truth": "9 bar",
            "correlated_wrong_value": "6 bar",
            "correct_report_is_independent": True,
            "conflict_flagging": "explicit hypothesis-set challenge before retrieval",
            "retrieval": {
                "k": 2,
                "group_by_source_root": True,
                "include_contested": True,
                "pool": "default (4*k)",
                "min_relevance": "default",
                "expand_lineage": "default",
            },
        },
        "scenarios": scenarios,
        "tests": {
            "junit": TEST_PATH.relative_to(ROOT).as_posix(),
            "reported_test_cases": cases,
            "failures": failures,
            "errors": errors,
            "skipped": skipped,
        },
        "limitations": [
            "This is a deterministic synthetic contract fixture, not a field prevalence or accuracy estimate.",
            "The test knows which value is correct; the store does not and keeps both alternatives in review.",
            "The conflict is explicitly challenged before retrieval; automatic semantic discovery of every contradiction is not established here.",
            "Copy recognition is exact-content containment in this fixture; paraphrase laundering is outside this task and is addressed separately by exposure-aware independence research.",
        ],
    }
    JSON_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# N5-08 minority-origin resilience fixture", "",
        "A single correct independent calibration report (9 bar) competes with one wrong source (6 bar) repeated through recognized exact copies. The conflict is explicitly opened for review before retrieval.", "",
        "| wrong copies | wrong agents / roots | correct roots | correct retrieved | exposed roots | evidence status | decision readiness |",
        "|---:|---:|---:|---|---:|---|---|",
    ]
    for row in scenarios:
        lines.append(
            f"| {row['correlated_wrong_copies']} | {row['wrong_reporting_agents']} / {row['wrong_source_roots']} | "
            f"{row['correct_source_roots']} | {row['correct_alternative_retrieved']} | "
            f"{row['distinct_source_roots_retrieved']} | {row['retrieval_evidence_validity']} | "
            f"{row['retrieval_decision_readiness']} |"
        )
    lines += ["", "Each scenario preserves exactly one independent wrong root and one independent correct root. The duplicated wrong reports are marked artificial support; the tie remains unresolved. Default root grouping keeps both roots in `k=2`, while contested evidence is exposed as invalid and the retrieval is flagged `review`. This fixture validates retention and review signaling, not truth discovery or automated resolution.", ""]
    MD_PATH.write_text("\n".join(lines), encoding="utf-8")
    return report


def main() -> int:
    report = run()
    print(json.dumps({"task_id": report["task_id"], "scenarios": len(report["scenarios"]),
                      "acceptance_passed": report["acceptance_passed"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

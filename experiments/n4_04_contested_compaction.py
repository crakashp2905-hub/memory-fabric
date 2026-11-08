"""Check minority-fact preservation through flat and hierarchical compaction."""
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
from memory_fabric.compaction import (  # noqa: E402
    compact_hierarchy,
    compact_session,
    verify_hierarchical_summary,
)
from memory_fabric.model import LifecycleState  # noqa: E402
from memory_fabric.validation import review_queue  # noqa: E402

JSON_PATH = ROOT / "research" / "results" / "n4-04-contested-compaction.json"
MD_PATH = ROOT / "research" / "results" / "n4-04-contested-compaction.md"
TEST_PATH = ROOT / "research" / "results" / "n4-04-contested-tests.xml"


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def _fixture(*, hold_suspicious: bool) -> tuple[MemoryFabric, str, list[str], str]:
    fabric = MemoryFabric(
        ":memory:", auto_activate=True, recognise_copies=False,
        hold_suspicious=hold_suspicious,
    )
    episode = fabric.start_episode("operator", "minority pressure report").id
    majority = [
        fabric.remember(
            "majority-log", "Pump P9 restart pressure is 6 bar.",
            source_episodes=[episode], scope="team",
        )
        for _ in range(10)
    ]
    minority = fabric.remember(
        "minority-inspector", "Pump P9 restart pressure is 9 bar.",
        source_episodes=[episode], scope="team",
    )
    return fabric, episode, majority, minority


def run() -> dict[str, Any]:
    junit_root = ET.parse(TEST_PATH).getroot()
    test_cases = len(list(junit_root.iter("testcase")))
    failures = len(list(junit_root.iter("failure")))
    errors = len(list(junit_root.iter("error")))
    skipped = len(list(junit_root.iter("skipped")))
    if test_cases != 3 or failures or errors or skipped:
        raise RuntimeError("N4-04 test evidence must contain three passing cases")

    flat_fabric, flat_episode, majority, minority = _fixture(hold_suspicious=False)
    try:
        flat_report = compact_session(flat_fabric, flat_episode, "compactor")
        flat_summary = flat_fabric.get(flat_report.summary_id)
        flat_text = flat_summary.content
        flat_sources = [flat_fabric.get(memory_id) for memory_id in [*majority, minority]]
        dependencies = flat_summary.context["summary_dependencies"]
        mapped_ids = {
            str(reference[0])
            for refs in dependencies.values()
            for reference in refs
        }
        flat_result = {
            "dispute_count": len(flat_report.disputes),
            "disputed_source_count": len(flat_report.disputes[0]) if flat_report.disputes else 0,
            "both_values_rendered": "6 bar" in flat_text and "9 bar" in flat_text,
            "explicitly_unresolved": "Disputed, unresolved" in flat_text,
            "all_source_ids_in_dependency_map": mapped_ids == {item.id for item in flat_sources},
            "summary_sha256": hashlib.sha256(flat_text.encode("utf-8")).hexdigest(),
        }
    finally:
        flat_fabric.close()

    hierarchy_fabric, hierarchy_episode, hierarchy_majority, hierarchy_minority = _fixture(
        hold_suspicious=False
    )
    try:
        hierarchy = compact_hierarchy(
            hierarchy_fabric, hierarchy_episode, "compactor", leaf_size=10
        )
        root = hierarchy_fabric.get(hierarchy.root_summary_id)
        leaf_minority = hierarchy_fabric.get(hierarchy.leaf_summary_ids[1])
        verified = verify_hierarchical_summary(hierarchy_fabric, hierarchy.root_summary_id)
        hierarchy_text = root.content
        hierarchy_result = {
            "leaf_sizes": [len(group) for group in hierarchy.leaf_source_groups],
            "minority_is_alone_in_second_leaf": hierarchy.leaf_source_groups[1] == [hierarchy_minority],
            "minority_leaf_contains_9_bar": "9 bar" in leaf_minority.content,
            "minority_leaf_contains_no_majority_6_bar": "6 bar" not in leaf_minority.content,
            "both_values_rendered_in_root": "6 bar" in hierarchy_text and "9 bar" in hierarchy_text,
            "root_explicitly_unresolved": "Disputed, unresolved" in hierarchy_text,
            "certificate_verified": bool(verified.get("certificate")),
            "source_count_verified": len(verified["source_versions"]) == 11,
            "root_sha256": hashlib.sha256(hierarchy_text.encode("utf-8")).hexdigest(),
        }
    finally:
        hierarchy_fabric.close()

    held_fabric, held_episode, _held_majority, held_minority = _fixture(hold_suspicious=True)
    try:
        held_memory = held_fabric.get(held_minority)
        held_report = compact_session(held_fabric, held_episode, "compactor")
        held_summary = held_fabric.get(held_report.summary_id)
        held_result = {
            "minority_lifecycle": held_memory.lifecycle_state.value,
            "minority_left_out_state": held_report.left_out.get(held_minority),
            "minority_remains_in_review_queue": held_minority in {
                assessment.memory_id for assessment in review_queue(held_fabric)
            },
            "active_summary_excludes_held_alternative": "9 bar" not in held_summary.content,
            "minority_not_promoted": held_fabric.get(held_minority).lifecycle_state
            is not LifecycleState.ACTIVE,
        }
    finally:
        held_fabric.close()

    checks = [
        *flat_result.values(),
        *hierarchy_result.values(),
        *[
            held_result["minority_remains_in_review_queue"],
            held_result["active_summary_excludes_held_alternative"],
            held_result["minority_not_promoted"],
        ],
    ]
    if not all(checks):
        raise RuntimeError("contested compaction oracle failed")

    result = {
        "schema": "memory-fabric-n4-04-contested-compaction/1",
        "task_id": "N4-04",
        "acceptance_passed": True,
        "evidence_level": "CONTRACT",
        "source": {
            "commit": _git("rev-parse", "HEAD"),
            "dirty_before_result_write": bool(_git("status", "--porcelain")),
            "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        },
        "fixture": {
            "majority_assertion_count": 10,
            "minority_assertion_count": 1,
            "majority_value": "6 bar",
            "minority_value": "9 bar",
            "flat_and_hierarchical_sources_pre_admitted": True,
            "hold_suspicious_disabled_only_for_preservation_cases": True,
        },
        "flat_compaction": flat_result,
        "hierarchical_compaction": hierarchy_result,
        "default_hold_safety": held_result,
        "tests": {
            "junit": TEST_PATH.relative_to(ROOT).as_posix(),
            "reported_test_cases": test_cases,
            "failures": failures,
            "errors": errors,
            "skipped": skipped,
        },
        "limitations": [
            "The 10:1 compaction cases exercise already exposable competing evidence by disabling write-time suspicion holding in the fixture; they do not assert either value is true.",
            "With default suspicion holding, the minority remains a candidate in the review queue and is deliberately excluded from the active summary until reviewed.",
            "Local in-memory contract evidence; no distributed or real-agent efficacy claim.",
        ],
    }
    JSON_PATH.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    MD_PATH.write_text(
        "# N4-04 contested-compaction evidence\n\n"
        "A 10:1 fixture verifies that flat and hierarchical compaction retain both "
        "values and render the conflict as unresolved. In the hierarchy, all ten "
        "majority reports occupy one leaf and the lone alternative occupies its "
        "own leaf; the certified root still renders and maps both alternatives.\n\n"
        "The default-hold control keeps the minority assertion in CANDIDATE state "
        "and in the review queue, while excluding it from the active summary. "
        "This prevents compaction from turning an unreviewed candidate into an "
        "actionable fact. See the JSON for exact checks, source binding, and limits.\n",
        encoding="utf-8",
    )
    return result


def main() -> int:
    result = run()
    print(json.dumps({
        "flat_compaction": result["flat_compaction"],
        "hierarchical_compaction": result["hierarchical_compaction"],
        "default_hold_safety": result["default_hold_safety"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Measure preservation of source identity and valid time through compaction."""
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

JSON_PATH = ROOT / "research" / "results" / "n4-05-temporal-compaction.json"
MD_PATH = ROOT / "research" / "results" / "n4-05-temporal-compaction.md"
TEST_PATH = ROOT / "research" / "results" / "n4-05-temporal-tests.xml"


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
    if cases < 2 or failures or errors or skipped:
        raise RuntimeError("N4-05 tests must pass with no skips")

    fabric = MemoryFabric(
        ":memory:", auto_activate=True, hold_suspicious=False,
        recognise_copies=False,
    )
    try:
        episode = fabric.start_episode("preference-owner", "room lighting").id
        current = fabric.remember(
            "preference-owner",
            "User U1 prefers warm white lighting.",
            source_episodes=[episode], scope="team",
            valid_from=2_000_000_000_000,
        )
        older_valid = fabric.remember(
            "preference-owner",
            "User U1 prefers cool white lighting.",
            source_episodes=[episode], scope="team",
            valid_from=1_000_000_000_000,
            valid_to=1_500_000_000_000,
        )
        corrected = fabric.revise(
            current,
            "User U1 prefers amber white lighting.",
            agent_id="reviewer",
            reason="preference clarified before installation",
            expected_version=1,
        )
        report = compact_session(fabric, episode, "compactor")
        summary = fabric.get(report.summary_id)
        metadata = summary.context["summary_source_metadata"]
        by_id = {item["source_id"]: item for item in metadata}
        earlier_world_time = 1_200_000_000_000
        later_world_time = 2_100_000_000_000
        temporal = {
            "content_keeps_revised_and_expired_alternatives": (
                "amber white lighting" in summary.content
                and "cool white lighting" in summary.content
            ),
            "content_drops_superseded_preference_text": "warm white lighting" not in summary.content,
            "current_version_identity_preserved": (
                by_id[current]["source_version"] == 2
                and by_id[current]["version_author"] == "reviewer"
            ),
            "transaction_order_uses_authoritative_log_sequence": (
                by_id[current]["recorded_seq"]
                > by_id[older_valid]["recorded_seq"]
            ),
            "corrected_valid_time_preserved": (
                by_id[current]["valid_from"] == 2_000_000_000_000
                and by_id[current]["valid_to"] is None
            ),
            "later_recorded_expired_claim_keeps_its_interval": (
                by_id[older_valid]["valid_from"] == 1_000_000_000_000
                and by_id[older_valid]["valid_to"] == 1_500_000_000_000
            ),
            "world_time_not_record_order_selects_applicability": (
                not fabric.get(current).applies_at(earlier_world_time)
                and fabric.get(older_valid).applies_at(earlier_world_time)
                and fabric.get(current).applies_at(later_world_time)
                and not fabric.get(older_valid).applies_at(later_world_time)
                and corrected.version == 2
            ),
            "source_ids_and_versions_match_summary_parents": {
                (item["source_id"], item["source_version"]) for item in metadata
            } == set(summary.provenance.parents),
        }
    finally:
        fabric.close()

    hierarchy_fabric = MemoryFabric(
        ":memory:", auto_activate=True, hold_suspicious=False,
        recognise_copies=False,
    )
    try:
        episode = hierarchy_fabric.start_episode("maintainer", "temporal history").id
        source_ids = [
            hierarchy_fabric.remember(
                "maintainer",
                f"Pump P{index} service interval is {index + 1} days.",
                source_episodes=[episode], scope="team",
                valid_from=1_000 + index, valid_to=2_000 + index,
            )
            for index in range(5)
        ]
        hierarchy = compact_hierarchy(
            hierarchy_fabric, episode, "compactor", leaf_size=2
        )
        root = hierarchy_fabric.get(hierarchy.root_summary_id)
        verified = verify_hierarchical_summary(hierarchy_fabric, root.id)
        metadata = root.context["summary_source_metadata"]
        metadata_by_id = {item["source_id"]: item for item in metadata}
        hierarchy_result = {
            "source_metadata_count": len(metadata),
            "source_ids_preserved": {item["source_id"] for item in metadata} == set(source_ids),
            "version_authors_preserved": all(
                item["version_author"] == "maintainer" for item in metadata
            ),
            "valid_intervals_preserved": all(
                metadata_by_id[source_id]["valid_from"] == 1_000 + index
                and metadata_by_id[source_id]["valid_to"] == 2_000 + index
                for index, source_id in enumerate(source_ids)
            ),
            "certificate_verifies_temporal_metadata": bool(verified.get("certificate")),
        }
    finally:
        hierarchy_fabric.close()

    if not all(temporal.values()) or not all(hierarchy_result.values()):
        raise RuntimeError("N4-05 temporal compaction oracle failed")
    result = {
        "schema": "memory-fabric-n4-05-temporal-compaction/1",
        "task_id": "N4-05",
        "acceptance_passed": True,
        "evidence_level": "CONTRACT",
        "source": {
            "commit": _git("rev-parse", "HEAD"),
            "dirty_before_result_write": bool(_git("status", "--porcelain")),
            "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        },
        "flat_temporal_preference": temporal,
        "hierarchical_metadata": hierarchy_result,
        "tests": {
            "junit": TEST_PATH.relative_to(ROOT).as_posix(),
            "reported_test_cases": cases,
            "failures": failures,
            "errors": errors,
            "skipped": skipped,
        },
        "limitations": [
            "Recorded timestamps and valid-time intervals are retained as metadata; the summary does not decide which preference applies without a requested world time.",
            "Local in-memory contract evidence, not a real-user preference-resolution benchmark.",
        ],
    }
    JSON_PATH.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    MD_PATH.write_text(
        "# N4-05 temporal compaction evidence\n\n"
        "The fixture revises a future-valid preference after recording an older, "
        "already-expired preference. The summary keeps the revised text and the "
        "older alternative, while per-source metadata retains exact ID/version, "
        "version author, recorded time, and the half-open valid-time interval. "
        "Applicability is checked at a declared world time; transaction order is "
        "not used as a truth rule. Hierarchical certificates also verify the "
        "source metadata. See the JSON for checks and limits.\n",
        encoding="utf-8",
    )
    return result


def main() -> int:
    result = run()
    print(json.dumps({
        "flat_temporal_preference": result["flat_temporal_preference"],
        "hierarchical_metadata": result["hierarchical_metadata"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

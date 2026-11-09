"""Demonstrate that competing claims remain unresolved despite unequal repetition."""
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
from memory_fabric.events import EventType  # noqa: E402
from memory_fabric.model import LifecycleState  # noqa: E402
from memory_fabric.consensus import support  # noqa: E402

JSON_PATH = ROOT / "research" / "results" / "n5-02-hypothesis-preservation.json"
MD_PATH = ROOT / "research" / "results" / "n5-02-hypothesis-preservation.md"
TEST_PATH = ROOT / "research" / "results" / "n5-02-hypothesis-tests.xml"


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
    if cases < 4 or failures or errors or skipped:
        raise RuntimeError("N5-02 tests must pass with no skips")

    fabric = MemoryFabric(
        auto_activate=True, hold_suspicious=False, recognise_copies=True
    )
    try:
        repeated = [
            fabric.remember(
                f"repeat_{index}", "Pump P9 restart pressure is 6 bar."
            )
            for index in range(10)
        ]
        independent = [
            fabric.remember(
                "inspector_a", "Pump P9 restart pressure measured at 9 bar."
            ),
            fabric.remember(
                "inspector_b", "Field check: P9 restarts at pressure 9 bar."
            ),
        ]
        before = support(fabric, "Pump P9 restart pressure is 6 bar.")
        six = next(value for value in before.values if value.value == "6")
        nine = next(value for value in before.values if value.value == "9")
        set_id = fabric.challenge(
            repeated + independent,
            evidence="contradictory pressure reports; no adjudication performed",
        )
        hset = fabric.state.hypothesis_sets[set_id]
        sources = {
            "6": sorted({fabric.source_root(mid) for mid in repeated}),
            "9": sorted({fabric.source_root(mid) for mid in independent}),
        }
        all_contested = all(
            fabric.get(mid).lifecycle_state is LifecycleState.CONTESTED
            for mid in repeated + independent
        )
        experiment_events = fabric.log.read_types([EventType.EXPERIMENT_RUN])
        result_fixture = {
            "six_bar": six.to_json(),
            "nine_bar": nine.to_json(),
            "claim_support_leading_before_challenge": before.leading,
            "hypothesis_set_id": set_id,
            "hypothesis_set_resolved": hset.resolved,
            "hypothesis_set_member_count": len(hset.memory_ids),
            "hypothesis_source_roots": sources,
            "all_members_contested": all_contested,
            "automatic_experiment_events": len(experiment_events),
            "both_values_preserved": (
                any("6 bar" in fabric.get(mid).content for mid in hset.memory_ids)
                and any("9 bar" in fabric.get(mid).content for mid in hset.memory_ids)
            ),
        }
    finally:
        fabric.close()

    if not (
        result_fixture["six_bar"]["independent_sources"] == 1
        and result_fixture["nine_bar"]["independent_sources"] == 2
        and result_fixture["hypothesis_set_resolved"] is False
        and result_fixture["hypothesis_set_member_count"] == 12
        and result_fixture["all_members_contested"]
        and result_fixture["automatic_experiment_events"] == 0
        and result_fixture["both_values_preserved"]
    ):
        raise RuntimeError("N5-02 disagreement preservation oracle failed")
    result = {
        "schema": "memory-fabric-n5-02-hypothesis-preservation/1",
        "task_id": "N5-02",
        "acceptance_passed": True,
        "evidence_level": "CONTRACT",
        "source": {
            "commit": _git("rev-parse", "HEAD"),
            "dirty_before_result_write": bool(_git("status", "--porcelain")),
            "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        },
        "fixture": result_fixture,
        "tests": {
            "junit": TEST_PATH.relative_to(ROOT).as_posix(),
            "reported_test_cases": cases,
            "failures": failures,
            "errors": errors,
            "skipped": skipped,
        },
        "limitations": [
            "The fixture demonstrates representation and non-resolution; it does not determine which pressure claim is true.",
            "Source-root counts inherit the repository's copy-recognition limits and do not establish source honesty.",
        ],
    }
    JSON_PATH.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    MD_PATH.write_text(
        "# N5-02 hypothesis preservation evidence\n\n"
        "The fixture has ten reporters repeating one 6 bar source and two "
        "independent 9 bar sources. Challenge opens an unresolved hypothesis "
        "set containing all twelve memories; each member remains contested, "
        "both values and their source roots remain represented, and no experiment "
        "or winner-resolution event is generated. The support ranking is not an "
        "authentication decision. See JSON for exact IDs and counts.\n",
        encoding="utf-8",
    )
    return result


def main() -> int:
    result = run()
    print(json.dumps(result["fixture"], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

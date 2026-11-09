"""Exercise lossy chatter removal with exact proof-edge verification."""
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
    CompactionRefused,
    compact_session,
    verify_compaction_certificate,
)

JSON_PATH = ROOT / "research" / "results" / "n4-08-lossy-compaction.json"
MD_PATH = ROOT / "research" / "results" / "n4-08-lossy-compaction.md"
TEST_PATH = ROOT / "research" / "results" / "n4-08-lossy-compaction-tests.xml"


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def _store() -> tuple[MemoryFabric, str]:
    fabric = MemoryFabric(
        ":memory:", auto_activate=True, hold_suspicious=False,
        recognise_copies=False,
    )
    return fabric, fabric.start_episode("operator", "lossy proof fixture").id


def run() -> dict[str, Any]:
    junit = ET.parse(TEST_PATH).getroot()
    cases = len(list(junit.iter("testcase")))
    failures = len(list(junit.iter("failure")))
    errors = len(list(junit.iter("error")))
    skipped = len(list(junit.iter("skipped")))
    if cases < 4 or failures or errors or skipped:
        raise RuntimeError("N4-08 focused tests must pass with no skips")

    fabric, episode = _store()
    try:
        fact_id = fabric.remember(
            "operator", "Pump P1 purge interval is 30 seconds.",
            source_episodes=[episode], scope="team",
        )
        chatter_id = fabric.remember(
            "operator", "The shift handover was pleasant.",
            source_episodes=[episode], scope="team",
        )
        report = compact_session(
            fabric, episode, "compactor",
            summarise=lambda memories, disputes: "Pump P1 purge interval is 30 seconds.",
        )
        if report.summary_id is None:
            raise RuntimeError("lossy compaction did not write a summary")
        summary = fabric.get(report.summary_id)
        verified = verify_compaction_certificate(fabric, summary.id)
        verified_versions = verified.get("source_versions")
        verified_dependencies = verified.get("dependencies")
        if not isinstance(verified_versions, list) or not isinstance(verified_dependencies, dict):
            raise RuntimeError("certificate verifier returned malformed evidence")
        accepted = {
            "nonconsequential_chatter_removed": "pleasant" not in summary.content,
            "source_versions_still_bound": {
                (str(pair[0]), int(pair[1])) for pair in verified_versions
            }
            == {(fact_id, 1), (chatter_id, 1)},
            "consequential_fact_edge_preserved": any(
                fact_id in [str(ref[0]) for ref in refs]
                for refs in verified_dependencies.values()
            ),
            "certificate": verified["certificate"],
        }
    finally:
        fabric.close()

    strict_fabric, strict_episode = _store()
    try:
        strict_fabric.remember(
            "operator", "Pump P1 purge interval is 30 seconds.",
            source_episodes=[strict_episode], scope="team",
        )
        strict_fabric.remember(
            "operator", "Valve V7 opens below 4 bar.",
            source_episodes=[strict_episode], scope="team",
        )
        before = set(strict_fabric.state.memories)
        try:
            compact_session(
                strict_fabric, strict_episode, "compactor",
                summarise=lambda memories, disputes: "Pump P1 purge interval is 30 seconds.",
            )
        except CompactionRefused as exc:
            refusal = str(exc)
        else:
            raise RuntimeError("strict compaction accepted a dropped proof edge")
        strict = {
            "dropped_fact_refused": True,
            "store_unchanged": set(strict_fabric.state.memories) == before,
            "reason": refusal,
        }
    finally:
        strict_fabric.close()

    if not all(accepted[key] for key in (
        "nonconsequential_chatter_removed",
        "source_versions_still_bound",
        "consequential_fact_edge_preserved",
    )) or not strict["store_unchanged"]:
        raise RuntimeError("N4-08 certificate acceptance failed")
    result = {
        "schema": "memory-fabric-n4-08-lossy-compaction/1",
        "task_id": "N4-08",
        "acceptance_passed": True,
        "evidence_level": "CONTRACT",
        "source": {
            "commit": _git("rev-parse", "HEAD"),
            "dirty_before_result_write": bool(_git("status", "--porcelain")),
            "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        },
        "lossy_nonconsequential_case": accepted,
        "strict_missing_edge_case": strict,
        "tests": {
            "junit": TEST_PATH.relative_to(ROOT).as_posix(),
            "reported_test_cases": cases,
            "failures": failures,
            "errors": errors,
            "skipped": skipped,
        },
        "limitations": [
            "The non-consequential classification is the repository's current fact-signature contract, not a universal semantic classifier.",
            "Certificate verification is local to the current in-memory store and does not claim distributed trust or external audit.",
        ],
    }
    JSON_PATH.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    MD_PATH.write_text(
        "# N4-08 lossy compaction evidence\n\n"
        "The fixture drops non-factual handover chatter while retaining every "
        "source version in the certificate and every consequential dependency "
        "edge. A second fixture attempts to drop a valve pressure fact; strict "
        "compaction refuses before writing a summary. See the JSON for exact "
        "certificate and refusal evidence. This is local contract evidence.\n",
        encoding="utf-8",
    )
    return result


def main() -> int:
    result = run()
    print(json.dumps({
        "lossy_nonconsequential_case": result["lossy_nonconsequential_case"],
        "strict_missing_edge_case": result["strict_missing_edge_case"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

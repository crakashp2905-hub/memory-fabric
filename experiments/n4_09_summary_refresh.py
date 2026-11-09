"""Profile affected-session summary refresh against all-session rebuilding."""
from __future__ import annotations

import hashlib
import json
import random
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from memory_fabric import MemoryFabric  # noqa: E402
from memory_fabric.compaction import compact_session, recompact  # noqa: E402

SEEDS = (13, 29, 43, 61, 79)
SESSION_COUNT = 6
FACTS_PER_SESSION = 8
CORRECTIONS = 3
ARMS = ("affected_refresh", "complete_rebuild")
JSON_PATH = ROOT / "research" / "results" / "n4-09-summary-refresh.json"
MD_PATH = ROOT / "research" / "results" / "n4-09-summary-refresh.md"
TEST_PATH = ROOT / "research" / "results" / "n4-09-summary-refresh-tests.xml"
PREREG_PATH = ROOT / "research" / "prereg" / "n4-09-summary-refresh-v1.md"


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _build(seed: int) -> tuple[MemoryFabric, list[str], list[list[str]]]:
    fabric = MemoryFabric(
        ":memory:", auto_activate=True, hold_suspicious=False,
        recognise_copies=False,
    )
    episodes: list[str] = []
    sources: list[list[str]] = []
    for session_index in range(SESSION_COUNT):
        episode = fabric.start_episode(
            "maintainer", f"rebuild session {session_index}"
        ).id
        episodes.append(episode)
        rows = list(range(FACTS_PER_SESSION))
        random.Random(seed * 100 + session_index).shuffle(rows)
        session_ids = []
        for index in rows:
            content = (
                f"Pump P{session_index} component C{index} pressure is "
                f"{20 + session_index + index} bar."
            )
            session_ids.append(fabric.remember(
                "maintainer", content, source_episodes=[episode], scope="team"
            ))
        # Correction targets are indexed by their content identity, independent
        # of the seeded source insertion order.
        by_component = {
            int(fabric.get(memory_id).content.split(" component C", 1)[1].split(" ", 1)[0]):
            memory_id
            for memory_id in session_ids
        }
        sources.append([by_component[index] for index in range(FACTS_PER_SESSION)])
    return fabric, episodes, sources


def _run_arm(seed: int, arm: str) -> dict[str, Any]:
    fabric, episodes, sources = _build(seed)
    current_summary_ids: dict[int, str] = {}
    initial_writes = 0
    for index, episode in enumerate(episodes):
        report = compact_session(fabric, episode, "compactor")
        if report.summary_id is None:
            raise RuntimeError("initial summary was not written")
        current_summary_ids[index] = report.summary_id
        initial_writes += 1

    corrections: list[dict[str, Any]] = []
    total_refresh_writes = 0
    total_inputs_reprocessed = 0
    unaffected_before = {
        index: _digest(fabric.get(summary_id).content)
        for index, summary_id in current_summary_ids.items()
    }
    for correction_index in range(CORRECTIONS):
        component = correction_index
        memory_id = sources[0][component]
        memory = fabric.get(memory_id)
        new_value = 100 + correction_index
        fabric.revise(
            memory_id,
            f"Pump P0 component C{component} pressure is {new_value} bar.",
            agent_id="reviewer",
            reason=f"source correction cycle {correction_index + 1}",
            expected_version=memory.version,
        )
        if arm == "affected_refresh":
            reports = recompact(fabric, "compactor")
        else:
            reports = [
                compact_session(fabric, episode, "compactor")
                for episode in episodes
            ]
        if any(report.summary_id is None for report in reports):
            raise RuntimeError("a correction refresh omitted a summary")
        if arm == "affected_refresh" and len(reports) != 1:
            raise RuntimeError("one source correction must refresh exactly one session")
        if arm == "complete_rebuild" and len(reports) != SESSION_COUNT:
            raise RuntimeError("complete rebuild did not rebuild every session")
        total_refresh_writes += len(reports)
        total_inputs_reprocessed += sum(len(report.inputs) for report in reports)
        if arm == "affected_refresh":
            current_summary_ids[0] = str(reports[0].summary_id)
        else:
            for index, report in enumerate(reports):
                current_summary_ids[index] = str(report.summary_id)
        current = fabric.get(current_summary_ids[0])
        if f"is {new_value} bar" not in current.content:
            raise RuntimeError("refreshed summary does not contain the corrected value")
        unaffected_unchanged = all(
            _digest(fabric.get(current_summary_ids[index]).content)
            == unaffected_before[index]
            for index in range(1, SESSION_COUNT)
        )
        if arm == "affected_refresh" and not unaffected_unchanged:
            raise RuntimeError("targeted refresh changed an unaffected summary")
        corrections.append({
            "correction_index": correction_index,
            "target_session": 0,
            "target_component": component,
            "writes": len(reports),
            "inputs_reprocessed": sum(len(report.inputs) for report in reports),
            "unaffected_summaries_unchanged": unaffected_unchanged,
            "affected_summary_sha256": _digest(current.content),
        })

    final_hashes = {
        str(index): _digest(fabric.get(summary_id).content)
        for index, summary_id in sorted(current_summary_ids.items())
    }
    active_current = all(
        fabric.get(summary_id).lifecycle_state.value == "active"
        for summary_id in current_summary_ids.values()
    )
    result = {
        "initial_summary_writes": initial_writes,
        "correction_refresh_writes": total_refresh_writes,
        "total_summary_writes": initial_writes + total_refresh_writes,
        "total_source_inputs_reprocessed_after_corrections": total_inputs_reprocessed,
        "correction_recomputations": corrections,
        "final_summary_sha256_by_session": final_hashes,
        "all_final_summaries_active": active_current,
    }
    fabric.close()
    return result


def evaluate_seed(seed: int) -> dict[str, Any]:
    incremental = _run_arm(seed, "affected_refresh")
    repeated = _run_arm(seed, "affected_refresh")
    full = _run_arm(seed, "complete_rebuild")
    deterministic = (
        incremental["final_summary_sha256_by_session"]
        == repeated["final_summary_sha256_by_session"]
        and [
            row["affected_summary_sha256"]
            for row in incremental["correction_recomputations"]
        ] == [
            row["affected_summary_sha256"]
            for row in repeated["correction_recomputations"]
        ]
    )
    if not deterministic or not incremental["all_final_summaries_active"]:
        raise RuntimeError("same-seed affected refresh is not deterministic and active")
    if not full["all_final_summaries_active"]:
        raise RuntimeError("complete rebuild left a final summary inactive")
    return {
        "seed": seed,
        "affected_refresh": incremental,
        "complete_rebuild": full,
        "same_seed_refresh_deterministic": deterministic,
    }


def run() -> dict[str, Any]:
    if not PREREG_PATH.is_file():
        raise RuntimeError("frozen N4-09 preregistration is missing")
    junit = ET.parse(TEST_PATH).getroot()
    cases = len(list(junit.iter("testcase")))
    failures = len(list(junit.iter("failure")))
    errors = len(list(junit.iter("error")))
    skipped = len(list(junit.iter("skipped")))
    if cases < 4 or failures or errors or skipped:
        raise RuntimeError("N4-09 focused tests must pass with no skips")
    seed_results = [evaluate_seed(seed) for seed in SEEDS]
    if any(
        row["writes"] != 1 or not row["unaffected_summaries_unchanged"]
        for result in seed_results
        for row in result["affected_refresh"]["correction_recomputations"]
    ):
        raise RuntimeError("affected summary recomputation was not bounded")
    if any(
        row["writes"] != SESSION_COUNT
        for result in seed_results
        for row in result["complete_rebuild"]["correction_recomputations"]
    ):
        raise RuntimeError("full rebuild arm did not cover all sessions")
    totals = {}
    for arm in ARMS:
        rows = [result[arm] for result in seed_results]
        totals[arm] = {
            "seed_count": len(rows),
            "mean_total_summary_writes": sum(row["total_summary_writes"] for row in rows) / len(rows),
            "mean_correction_refresh_writes": sum(row["correction_refresh_writes"] for row in rows) / len(rows),
            "mean_source_inputs_reprocessed_after_corrections": sum(
                row["total_source_inputs_reprocessed_after_corrections"] for row in rows
            ) / len(rows),
        }
    result = {
        "schema": "memory-fabric-n4-09-summary-refresh/1",
        "task_id": "N4-09",
        "acceptance_passed": True,
        "evidence_level": "CONTRACT",
        "source": {
            "commit": _git("rev-parse", "HEAD"),
            "dirty_before_result_write": bool(_git("status", "--porcelain")),
            "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "preregistration_sha256": hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest(),
        },
        "design": {
            "seeds": list(SEEDS), "sessions": SESSION_COUNT,
            "facts_per_session": FACTS_PER_SESSION,
            "corrections_per_seed": CORRECTIONS,
            "arms": list(ARMS),
            "refresh_semantics": "full rebuild of only affected sessions; no in-place patch",
        },
        "mean_metrics": totals,
        "seed_results": seed_results,
        "tests": {
            "junit": TEST_PATH.relative_to(ROOT).as_posix(),
            "reported_test_cases": cases,
            "failures": failures,
            "errors": errors,
            "skipped": skipped,
        },
        "limitations": [
            "Operation counts and content hashes are measured; wall-clock latency and production-scale behavior are not.",
            "Affected refresh rebuilds the full summary for each affected session rather than patching its text in place.",
            "Local in-memory fixture only; no distributed queue, concurrent corrections, or persistent database claim.",
        ],
    }
    JSON_PATH.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# N4-09 summary refresh profile", "",
        "**Evidence level:** `CONTRACT`; local deterministic operation-count study.",
        "", "| Arm | Mean writes after corrections | Mean total writes | Mean source inputs reprocessed |",
        "|---|---:|---:|---:|",
    ]
    for arm in ARMS:
        row = totals[arm]
        lines.append(
            f"| `{arm}` | {row['mean_correction_refresh_writes']:.1f} "
            f"| {row['mean_total_summary_writes']:.1f} "
            f"| {row['mean_source_inputs_reprocessed_after_corrections']:.1f} |"
        )
    lines.extend([
        "", "One of six sessions receives each of three corrections. The affected-refresh",
        "arm rebuilds one session summary per correction and leaves unaffected summaries",
        "unchanged. Same-seed final content hashes are identical across repeated runs.",
        "This is operation-count evidence, not a latency or production-scale claim.",
    ])
    MD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return result


def main() -> int:
    result = run()
    print(json.dumps(result["mean_metrics"], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

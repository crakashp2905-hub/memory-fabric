"""Reproduce strict, fail-closed token-budgeted compaction behavior."""
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
from memory_fabric.compaction import CompactionBudgetExceeded, compact_session  # noqa: E402
from memory_fabric.summary_dependencies import verify_stored_dependency_map  # noqa: E402

JSON_PATH = ROOT / "research" / "results" / "n4-06-budgeted-compaction.json"
MD_PATH = ROOT / "research" / "results" / "n4-06-budgeted-compaction.md"
TEST_PATH = ROOT / "research" / "results" / "n4-06-budget-tests.xml"
TOKENIZER = "test-whitespace-tokenizer/1"


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def _fabric() -> tuple[MemoryFabric, str, list[str]]:
    fabric = MemoryFabric(
        ":memory:", auto_activate=True, hold_suspicious=False,
        recognise_copies=False,
    )
    episode = fabric.start_episode("operator", "budgeted handoff").id
    source_ids = [
        fabric.remember(
            "operator", text, source_episodes=[episode], scope="team"
        )
        for text in (
            "Pump P1 purge interval is 30 seconds.",
            "Valve V7 opens below 4 bar.",
            "Pump P9 restart pressure is 6 bar.",
        )
    ]
    return fabric, episode, source_ids


def run() -> dict[str, Any]:
    junit = ET.parse(TEST_PATH).getroot()
    cases = len(list(junit.iter("testcase")))
    failures = len(list(junit.iter("failure")))
    errors = len(list(junit.iter("error")))
    skipped = len(list(junit.iter("skipped")))
    if cases != 4 or failures or errors or skipped:
        raise RuntimeError("N4-06 tests must contain four passing cases with no skips")

    def counter(text: str) -> int:
        return len(text.split())
    success_fabric, success_episode, success_sources = _fabric()
    try:
        success_report = compact_session(
            success_fabric,
            success_episode,
            "compactor",
            token_counter=counter,
            tokenizer_provenance=TOKENIZER,
            max_summary_tokens=100,
        )
        success_summary = success_fabric.get(success_report.summary_id)
        dependencies = verify_stored_dependency_map(
            success_summary,
            [success_fabric.get(memory_id) for memory_id in success_sources],
        )
        mapped = {
            str(memory_id)
            for refs in dependencies.values()
            for memory_id, _version in refs
        }
        fit_result = {
            "limit": success_report.max_summary_tokens,
            "observed_tokens": success_report.summary_token_estimate,
            "tokenizer_provenance": success_report.tokenizer_provenance,
            "status": success_report.token_budget_status,
            "all_required_source_ids_remain_dependencies": mapped == set(success_sources),
            "summary_written": True,
        }
    finally:
        success_fabric.close()

    failure_fabric, failure_episode, failure_sources = _fabric()
    try:
        before = set(failure_fabric.state.memories)
        try:
            compact_session(
                failure_fabric,
                failure_episode,
                "compactor",
                token_counter=counter,
                tokenizer_provenance=TOKENIZER,
                max_summary_tokens=1,
            )
        except CompactionBudgetExceeded as exc:
            failure = exc.to_dict()
        else:
            raise RuntimeError("over-budget compaction unexpectedly wrote a summary")
        failure_result = {
            **failure,
            "all_required_source_ids_reported": set(failure["required_source_ids"])
            == set(failure_sources),
            "store_unchanged": set(failure_fabric.state.memories) == before,
        }
    finally:
        failure_fabric.close()

    if not (
        fit_result["status"] == "WITHIN_BUDGET"
        and fit_result["observed_tokens"] <= fit_result["limit"]
        and fit_result["summary_written"]
        and fit_result["all_required_source_ids_remain_dependencies"]
    ) or not all(
        failure_result[key]
        for key in ("all_required_source_ids_reported", "store_unchanged")
    ):
        raise RuntimeError("N4-06 budget oracle failed")
    result = {
        "schema": "memory-fabric-n4-06-budgeted-compaction/1",
        "task_id": "N4-06",
        "acceptance_passed": True,
        "evidence_level": "CONTRACT",
        "source": {
            "commit": _git("rev-parse", "HEAD"),
            "dirty_before_result_write": bool(_git("status", "--porcelain")),
            "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        },
        "within_budget": fit_result,
        "over_budget_failure": failure_result,
        "tests": {
            "junit": TEST_PATH.relative_to(ROOT).as_posix(),
            "reported_test_cases": cases,
            "failures": failures,
            "errors": errors,
            "skipped": skipped,
        },
        "contract": {
            "all_usable_sources_are_compulsory": True,
            "partial_summary_never_written": True,
            "failure_reports_utf8_bytes_and_tokens_separately": True,
            "token_budget_requires_explicit_counter_and_provenance": True,
        },
        "limitations": [
            "This strict policy refuses the complete summary when it cannot fit; it does not silently omit optional sources.",
            "Token counts cover summary text only and exclude provider wrappers, prompts, and tool schemas.",
            "The test tokenizer is a deterministic fixture counter, not a model tokenizer or cost estimate.",
        ],
    }
    JSON_PATH.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    MD_PATH.write_text(
        "# N4-06 budgeted compaction evidence\n\n"
        "A token budget is checked against the complete summary using an explicit "
        "counter and provenance. Every usable source is compulsory. If the summary "
        "does not fit, the API returns a structured `CompactionBudgetExceeded` "
        "containing the required token count, UTF-8 byte counts, tokenizer identity, "
        "and all source IDs; the event store is unchanged. The compacted summary "
        "records its limit and observed count when it fits. See JSON for exact checks.\n",
        encoding="utf-8",
    )
    return result


def main() -> int:
    result = run()
    print(json.dumps({
        "within_budget": result["within_budget"],
        "over_budget_failure": result["over_budget_failure"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

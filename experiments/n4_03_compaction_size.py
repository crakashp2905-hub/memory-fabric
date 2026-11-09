"""Measure text bytes and optional model-token estimates for governed compaction.

Run from the repository root with ``python -m experiments.n4_03_compaction_size``.
Token counts cover each source text and the summary text only; provider message
wrappers, system prompts, and tool schemas are outside this local measurement.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from importlib.metadata import version
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from memory_fabric import MemoryFabric  # noqa: E402
from memory_fabric.compaction import compact_session  # noqa: E402

JSON_PATH = ROOT / "research" / "results" / "n4-03-compaction-size.json"
MD_PATH = ROOT / "research" / "results" / "n4-03-compaction-size.md"
TEST_XML_PATH = ROOT / "research" / "results" / "n4-03-compaction-tests.xml"
TEST_LOG_PATH = ROOT / "research" / "results" / "n4-03-compaction-tests.txt"


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def run() -> dict[str, Any]:
    junit_root = ET.parse(TEST_XML_PATH).getroot()
    test_cases = list(junit_root.iter("testcase"))
    test_output = TEST_LOG_PATH.read_text(encoding="utf-8")
    test_summary = re.search(r"(?P<cases>\d+) passed, (?P<subtests>\d+) subtests passed", test_output)
    if test_summary is None:
        raise RuntimeError("N4-03 pytest log lacks an explicit case/subtest summary")
    test_evidence = {
        "junit": TEST_XML_PATH.relative_to(ROOT).as_posix(),
        "console_log": TEST_LOG_PATH.relative_to(ROOT).as_posix(),
        "reported_test_cases": len(test_cases),
        "reported_subtests": int(test_summary.group("subtests")),
        "failures": len(list(junit_root.iter("failure"))),
        "errors": len(list(junit_root.iter("error"))),
        "skipped": len(list(junit_root.iter("skipped"))),
    }
    if not test_cases or test_evidence["failures"] or test_evidence["errors"]:
        raise RuntimeError("N4-03 test evidence is missing or contains failures/errors")

    token_counter = None
    tokenizer_provenance = None
    tokenizer_unavailable_reason = None
    try:
        import tiktoken

        encoding = tiktoken.get_encoding("cl100k_base")
        token_counter = lambda text: len(encoding.encode(text))  # noqa: E731
        tokenizer_provenance = f"tiktoken=={version('tiktoken')}; encoding=cl100k_base"
    except Exception as exc:  # Optional tokenizer initialization may need unavailable network data.
        tokenizer_unavailable_reason = (
            f"{type(exc).__name__}: tokenizer data could not be initialized; "
            "check the local cache or network availability"
        )

    fabric = MemoryFabric(":memory:", auto_activate=True, recognise_copies=False)
    try:
        episode = fabric.start_episode("operator", "N4-03 size measurement").id
        sources = [
            fabric.remember(
                "operator",
                f"Pump P{index} purge threshold is {index + 10} bar.",
                source_episodes=[episode],
                scope="team",
            )
            for index in range(8)
        ]
        report = compact_session(
            fabric,
            episode,
            "compactor",
            token_counter=token_counter,
            tokenizer_provenance=tokenizer_provenance,
        )
        summary = fabric.get(report.summary_id)
        source_texts = [fabric.get(memory_id).content for memory_id in sources]
        result = {
            "schema": "memory-fabric-n4-03-compaction-size/1",
            "task_id": "N4-03",
            "acceptance_passed": True,
            "evidence_level": "CONTRACT",
            "source": {
                "commit": _git("rev-parse", "HEAD"),
                "dirty_before_result_write": bool(_git("status", "--porcelain")),
                "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            },
            "fixture": {
                "source_memory_count": len(source_texts),
                "source_content_sha256": hashlib.sha256(
                    "\n".join(source_texts).encode("utf-8")
                ).hexdigest(),
                "summary_content_sha256": hashlib.sha256(summary.content.encode("utf-8")).hexdigest(),
            },
            "measurements": {
                "source_bytes_utf8": report.source_bytes_utf8,
                "summary_bytes_utf8": report.summary_bytes_utf8,
                "source_token_estimate": report.source_token_estimate,
                "summary_token_estimate": report.summary_token_estimate,
                "tokenizer_provenance": report.tokenizer_provenance,
                "token_measurement_status": report.token_measurement_status,
                "tokenizer_unavailable_reason": tokenizer_unavailable_reason,
                "token_scope": "sum of independently encoded source memory contents; summary content only",
                "provider_wrappers_included": False,
            },
            "interpretation": {
                "bytes_are_not_token_counts": True,
                "bytes_are_not_model_cost": True,
                "token_counts_are_not_end_to_end_request_usage": True,
            },
            "tests": test_evidence,
        }
    finally:
        fabric.close()
    JSON_PATH.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    measurements = result["measurements"]
    token_label = (
        f"{measurements['source_token_estimate']} source / "
        f"{measurements['summary_token_estimate']} summary tokens"
        if measurements["token_measurement_status"] == "MEASURED"
        else "NOT MEASURED: " + str(measurements["tokenizer_unavailable_reason"] or "no tokenizer available")
    )
    MD_PATH.write_text(
        "# N4-03 compaction size measurement\n\n"
        f"Source payload: {measurements['source_bytes_utf8']} UTF-8 bytes; "
        f"summary: {measurements['summary_bytes_utf8']} UTF-8 bytes.\n\n"
        f"Tokenizer result: {token_label}. Provenance: "
        f"{measurements['tokenizer_provenance'] or 'none'}.\n\n"
        "Token counts, when present, cover only the independently encoded source "
        "memory contents and summary text. Provider wrappers, prompts, and tool "
        "schemas are excluded. Byte counts are not token counts and imply no model "
        "cost. See the JSON artifact for exact source and fixture digests.\n",
        encoding="utf-8",
    )
    return result


def main() -> int:
    result = run()
    print(json.dumps(result["measurements"], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

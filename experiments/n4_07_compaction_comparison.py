"""Compare four deterministic context-building arms on temporal tasks.

This is a simulated agent contract benchmark, not a real-agent evaluation.
"""
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
from memory_fabric.compaction import compact_session  # noqa: E402
from memory_fabric.summary_dependencies import verify_stored_dependency_map  # noqa: E402

SEEDS = (11, 23, 37, 41, 59)
SUBJECTS = ("U1", "U2", "U3", "U4")
VALUES = {
    "U1": ("warm", "cool"),
    "U2": ("quiet", "loud"),
    "U3": ("bright", "dim"),
    "U4": ("firm", "soft"),
}
QUERY_TIMES = (50, 150)
RECENCY_RECORD_CAP = 6
ARMS = (
    "no_compaction",
    "naive_recency",
    "extractive_summary",
    "provenance_preserving_summary",
)
JSON_PATH = ROOT / "research" / "results" / "n4-07-compaction-comparison.json"
MD_PATH = ROOT / "research" / "results" / "n4-07-compaction-comparison.md"
TEST_PATH = ROOT / "research" / "results" / "n4-07-compaction-tests.xml"
PREREG_PATH = ROOT / "research" / "prereg" / "n4-07-compaction-comparison-v1.md"


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def _json_bytes(value: Any) -> int:
    return len(json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8"))


def _fixture(seed: int) -> tuple[MemoryFabric, str, list[str], list[dict[str, Any]]]:
    fabric = MemoryFabric(
        ":memory:", auto_activate=True, hold_suspicious=False,
        recognise_copies=False,
    )
    episode = fabric.start_episode("simulated-agent", f"temporal handoff seed {seed}").id
    rows: list[dict[str, Any]] = []
    for subject in SUBJECTS:
        earlier, later = VALUES[subject]
        rows.extend((
            {
                "subject": subject, "value": earlier, "valid_from": 0,
                "valid_to": 100,
                "content": f"User {subject} prefers {earlier} lighting.",
            },
            {
                "subject": subject, "value": later, "valid_from": 100,
                "valid_to": 200,
                "content": f"User {subject} prefers {later} lighting.",
            },
        ))
    rows.extend({
        "subject": None, "value": None, "valid_from": None, "valid_to": None,
        "content": f"Handover checklist item {index} is reviewed for seed {seed}.",
    } for index in range(8))
    random.Random(seed).shuffle(rows)
    source_ids: list[str] = []
    for row in rows:
        kwargs: dict[str, Any] = {
            "source_episodes": [episode], "scope": "team",
        }
        if row["subject"] is not None:
            kwargs.update(valid_from=row["valid_from"], valid_to=row["valid_to"])
        source_ids.append(fabric.remember("fixture-source", row["content"], **kwargs))
    return fabric, episode, source_ids, rows


def _raw_choice(records: list[Any], subject: str, when: int) -> str | None:
    import re

    applicable = []
    for memory in records:
        match = re.search(rf"User {subject} prefers ([a-z]+) lighting", memory.content)
        if match and memory.applies_at(when):
            applicable.append(match.group(1))
    return applicable[0] if len(applicable) == 1 else None


def _text_choice(text: str, subject: str) -> str | None:
    import re

    values = re.findall(rf"User {subject} prefers ([a-z]+) lighting", text)
    return values[-1] if values else None


def _expected(subject: str, when: int) -> str:
    return VALUES[subject][0 if when < 100 else 1]


def _metrics(records: list[Any], all_sources: list[Any],
             expected_ids: set[tuple[str, int]],
             payload_text: str, payload_bytes: int, total_source_bytes: int,
             tasks: list[dict[str, Any]], choice_fn: Any) -> dict[str, Any]:
    successes = 0
    stale = 0
    abstentions = 0
    for task in tasks:
        choice = choice_fn(task)
        if choice is None:
            abstentions += 1
        elif choice != _expected(task["subject"], task["when"]):
            stale += 1
        else:
            successes += 1
    recovered_pairs = {(memory.id, memory.version) for memory in all_sources
                       if memory.id in payload_text}
    fidelity = len(recovered_pairs & expected_ids) / len(expected_ids)
    source_texts = {memory.content for memory in all_sources}
    factual_fidelity = sum(text in payload_text for text in source_texts) / max(1, len(source_texts))
    total = len(tasks)
    return {
        "task_count": total,
        "task_successes": successes,
        "task_success_rate": successes / total,
        "false_stale_actions": stale,
        "false_stale_action_rate": stale / total,
        "abstentions": abstentions,
        "context_bytes_utf8": payload_bytes,
        "compression_factor": total_source_bytes / payload_bytes,
        "source_identity_reconstruction_fidelity": fidelity,
        "factual_text_reconstruction_fidelity": min(1.0, factual_fidelity),
    }


def evaluate_seed(seed: int) -> dict[str, Any]:
    fabric, episode, source_ids, _rows = _fixture(seed)
    try:
        sources = [fabric.get(memory_id) for memory_id in source_ids]
        source_payload = {"records": [memory.to_json() for memory in sources]}
        total_source_bytes = _json_bytes(source_payload)
        expected_ids = {(memory.id, memory.version) for memory in sources}
        tasks = [
            {"subject": subject, "when": when}
            for subject in SUBJECTS for when in QUERY_TIMES
        ]
        arms: dict[str, dict[str, Any]] = {}

        arms["no_compaction"] = _metrics(
            sources, sources, expected_ids, json.dumps(source_payload, ensure_ascii=False),
            total_source_bytes, total_source_bytes, tasks,
            lambda task: _raw_choice(sources, task["subject"], task["when"]),
        )

        recent = sources[-RECENCY_RECORD_CAP:]
        recent_payload = {"records": [memory.to_json() for memory in recent]}
        recent_bytes = _json_bytes(recent_payload)
        arms["naive_recency"] = _metrics(
            recent, sources, expected_ids, json.dumps(recent_payload, ensure_ascii=False),
            recent_bytes, total_source_bytes, tasks,
            lambda task: _raw_choice(recent, task["subject"], task["when"]),
        )

        report = compact_session(fabric, episode, "simulated-compactor")
        if report.summary_id is None:
            raise RuntimeError("compaction did not write a summary")
        summary = fabric.get(report.summary_id)
        text_payload = summary.content
        arms["extractive_summary"] = _metrics(
            [], sources, expected_ids, text_payload, len(text_payload.encode("utf-8")),
            total_source_bytes, tasks,
            lambda task: _text_choice(text_payload, task["subject"]),
        )

        metadata = summary.context.get("summary_source_metadata")
        if not isinstance(metadata, list):
            raise RuntimeError("summary omitted source metadata")
        dep_map = verify_stored_dependency_map(summary, sources)
        mapped = {
            (str(memory_id), int(version))
            for references in dep_map.values()
            for memory_id, version in references
        }
        if mapped != expected_ids:
            raise RuntimeError("provenance summary does not preserve all source versions")
        metadata_by_id = {str(item["source_id"]): item for item in metadata}
        if set(metadata_by_id) != set(source_ids):
            raise RuntimeError("source metadata does not cover the full fixture")
        for memory_id, item in metadata_by_id.items():
            source = fabric.get(memory_id)
            if (
                int(item["source_version"]) != source.version
                or item["valid_from"] != source.valid_from
                or item["valid_to"] != source.valid_to
            ):
                raise RuntimeError("summary temporal metadata differs from its source")
        versioned_sources = [
            fabric.get(memory_id)
            for memory_id, item in metadata_by_id.items()
            if int(item["source_version"]) == fabric.get(memory_id).version
        ]
        preserved_payload = {
            "text": summary.content,
            "source_metadata": metadata,
            "dependency_map": dep_map,
        }
        preserved_text = json.dumps(preserved_payload, ensure_ascii=False, sort_keys=True)
        arms["provenance_preserving_summary"] = _metrics(
            versioned_sources, sources, expected_ids, preserved_text,
            _json_bytes(preserved_payload), total_source_bytes, tasks,
            lambda task: _raw_choice(
                versioned_sources, task["subject"], task["when"]
            ),
        )

        if arms["no_compaction"]["task_success_rate"] != 1.0:
            raise RuntimeError("full-history baseline failed its temporal oracle")
        if arms["provenance_preserving_summary"]["false_stale_actions"] != 0:
            raise RuntimeError("provenance-preserving arm emitted a false stale action")
        if any(arms[name]["task_success_rate"] > arms["no_compaction"]["task_success_rate"]
               for name in ARMS):
            raise RuntimeError("an arm exceeded the full-history baseline")
        return {"seed": seed, "task_count": len(tasks), "arms": arms,
                "dependency_map_verified": True}
    finally:
        fabric.close()


def run() -> dict[str, Any]:
    if not PREREG_PATH.is_file():
        raise RuntimeError("frozen N4-07 preregistration is missing")
    junit = ET.parse(TEST_PATH).getroot()
    cases = len(list(junit.iter("testcase")))
    failures = len(list(junit.iter("failure")))
    errors = len(list(junit.iter("error")))
    skipped = len(list(junit.iter("skipped")))
    if cases < 4 or failures or errors or skipped:
        raise RuntimeError("N4-07 focused tests must pass with no skips")

    seed_results = [evaluate_seed(seed) for seed in SEEDS]
    aggregate: dict[str, dict[str, float | int]] = {}
    for arm in ARMS:
        seed_metrics = [result["arms"][arm] for result in seed_results]
        aggregate[arm] = {
            "task_count": sum(int(item["task_count"]) for item in seed_metrics),
            "task_successes": sum(int(item["task_successes"]) for item in seed_metrics),
            "task_success_rate": sum(float(item["task_success_rate"]) for item in seed_metrics) / len(seed_metrics),
            "false_stale_actions": sum(int(item["false_stale_actions"]) for item in seed_metrics),
            "false_stale_action_rate": sum(float(item["false_stale_action_rate"]) for item in seed_metrics) / len(seed_metrics),
            "abstentions": sum(int(item["abstentions"]) for item in seed_metrics),
            "mean_context_bytes_utf8": sum(int(item["context_bytes_utf8"]) for item in seed_metrics) / len(seed_metrics),
            "mean_compression_factor": sum(float(item["compression_factor"]) for item in seed_metrics) / len(seed_metrics),
            "mean_source_identity_reconstruction_fidelity": sum(float(item["source_identity_reconstruction_fidelity"]) for item in seed_metrics) / len(seed_metrics),
            "mean_factual_text_reconstruction_fidelity": sum(float(item["factual_text_reconstruction_fidelity"]) for item in seed_metrics) / len(seed_metrics),
        }
    dataset = {
        "seeds": list(SEEDS), "subjects": list(SUBJECTS),
        "values": VALUES, "query_times": list(QUERY_TIMES),
        "record_cap": RECENCY_RECORD_CAP, "tasks_per_seed": 8,
    }
    dataset_digest = hashlib.sha256(json.dumps(
        dataset, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()
    result = {
        "schema": "memory-fabric-n4-07-compaction-comparison/1",
        "task_id": "N4-07",
        "acceptance_passed": True,
        "evidence_level": "SIMULATED",
        "simulation_label": "DETERMINISTIC_SYNTHETIC_AGENT_CONTRACT",
        "source": {
            "commit": _git("rev-parse", "HEAD"),
            "dirty_before_result_write": bool(_git("status", "--porcelain")),
            "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "preregistration_sha256": hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest(),
        },
        "preregistration": PREREG_PATH.relative_to(ROOT).as_posix(),
        "dataset": {**dataset, "sha256": dataset_digest},
        "arms": aggregate,
        "seed_results": seed_results,
        "tests": {
            "junit": TEST_PATH.relative_to(ROOT).as_posix(),
            "reported_test_cases": cases,
            "failures": failures,
            "errors": errors,
            "skipped": skipped,
        },
        "interpretation": [
            "This is a simulated contract fixture, not a real-agent evaluation.",
            "UTF-8 byte counts are context-payload size proxies, not token or cost estimates.",
            "No superiority claim is made; the full-history baseline is a fixture ceiling.",
        ],
    }
    JSON_PATH.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# N4-07 compaction comparison",
        "",
        "**Evidence level:** `SIMULATED` — deterministic synthetic agent contract.",
        "**Seeds:** `11, 23, 37, 41, 59`; **tasks:** 40 per arm.",
        "",
        "| Arm | Success | False stale actions | Mean bytes | Compression factor | Identity fidelity | Factual fidelity |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for arm in ARMS:
        item = aggregate[arm]
        lines.append(
            f"| `{arm}` | {item['task_success_rate']:.3f} | {item['false_stale_actions']} "
            f"| {item['mean_context_bytes_utf8']:.1f} | {item['mean_compression_factor']:.3f} "
            f"| {item['mean_source_identity_reconstruction_fidelity']:.3f} "
            f"| {item['mean_factual_text_reconstruction_fidelity']:.3f} |"
        )
    lines.extend([
        "",
        "This is a descriptive fixture comparison, not evidence of real-agent efficacy.",
        "Byte counts are UTF-8 payload sizes and are not token or model-cost estimates.",
        "The full-history arm is a fixture ceiling; any method above it invalidates the run.",
        "Exact inputs, per-seed values, test status, and source provenance are in the JSON.",
    ])
    MD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return result


def main() -> int:
    result = run()
    print(json.dumps(result["arms"], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Summarize observed dispositions in the frozen prompt-injection corpus."""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from memory_fabric import LifecycleState, MemoryFabric  # noqa: E402
from memory_fabric.governance.firewall import Firewall  # noqa: E402
from memory_fabric.governance.injection import InjectionDetector  # noqa: E402

CORPUS = ROOT / "tests" / "data" / "prompt_injection_corpus.json"
OUT = ROOT / "research" / "results" / "h1-10-injection-outcomes.json"


def build_report() -> dict[str, object]:
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    detector = InjectionDetector()
    firewall = Firewall()
    fabric = MemoryFabric(":memory:")
    rows = []
    by_family: dict[str, list[dict[str, object]]] = defaultdict(list)
    try:
        for case in corpus["cases"]:
            finding_kinds = sorted({finding.kind for finding in detector.scan(case["text"])})
            decision = firewall.screen_ingest(case["text"]).decision.value
            memory_id = fabric.remember("corpus-agent", case["text"])
            lifecycle = fabric.lifecycle_of(memory_id).value
            false_withheld = case["family"] == "near_miss" and lifecycle == "quarantined"
            row = {
                "id": case["id"], "family": case["family"],
                "detector_kinds": finding_kinds,
                "observed_decision": decision,
                "observed_lifecycle": lifecycle,
                "expected_decision": case["expected_decision"],
                "expected_lifecycle": case["expected_lifecycle"],
                "matches_fixture_expectation": (
                    decision == case["expected_decision"] and lifecycle == case["expected_lifecycle"]),
                "false_withheld_near_miss": false_withheld,
                "screening_gap_non_authoritative_candidate": (
                    case["family"] in {"source_laundering", "encoded_payload"}
                    and lifecycle == LifecycleState.CANDIDATE.value),
                "interpretation": case.get("interpretation", ""),
            }
            rows.append(row)
            by_family[case["family"]].append(row)
    finally:
        fabric.close()
    summary = {}
    for family, cases in sorted(by_family.items()):
        summary[family] = {
            "cases": len(cases),
            "quarantined": sum(row["observed_lifecycle"] == "quarantined" for row in cases),
            "candidate": sum(row["observed_lifecycle"] == "candidate" for row in cases),
            "false_withheld_near_misses": sum(row["false_withheld_near_miss"] for row in cases),
            "screening_gap_candidates": sum(
                row["screening_gap_non_authoritative_candidate"] for row in cases),
        }
    return {
        "schema": "mf-prompt-injection-outcomes/1",
        "population": "CONTRACT",
        "corpus_schema": corpus["schema"],
        "total_cases": len(rows),
        "fixture_expectations_matched": sum(row["matches_fixture_expectation"] for row in rows),
        "false_withheld_near_misses": sum(row["false_withheld_near_miss"] for row in rows),
        "screening_gap_non_authoritative_candidates": sum(
            row["screening_gap_non_authoritative_candidate"] for row in rows),
        "by_family": summary,
        "cases": rows,
        "limitations": [
            "Eight deterministic cases are too small and templated to estimate real-world precision or recall.",
            "A candidate may be visible as data; the report does not measure downstream model compliance.",
            "Near-miss quarantine counts are observed false-withholding examples, not a population rate.",
            "Source laundering and encoded content that remain candidates are screening gaps, not proof of successful action or privilege escalation.",
        ],
        "claim_boundary": "No prompt-injection-proof claim is supported by this experiment.",
    }


def main() -> int:
    report = build_report()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in (
        "schema", "total_cases", "fixture_expectations_matched",
        "false_withheld_near_misses", "screening_gap_non_authoritative_candidates",
        "by_family", "claim_boundary")}, indent=2))
    return 0 if report["fixture_expectations_matched"] == report["total_cases"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

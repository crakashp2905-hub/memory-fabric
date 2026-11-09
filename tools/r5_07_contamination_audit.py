"""Audit synthetic benchmark text, IDs, and tool names for scenario labels."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from experiments.r4_05_adversarial_cases import build_cases

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = ("supported", "corrected", "contested", "missing", "near-miss",
             "distractor", "current", "superseded", "answer", "gold")
TOOL_NAMES = ("publish", "archive", "notify")


def audit_dataset(cases: list[dict[str, Any]], tool_names: tuple[str, ...] = TOOL_NAMES) -> dict[str, Any]:
    findings = []
    scanned = {"case_ids": 0, "memory_ids": 0, "memory_texts": 0,
               "tool_names": len(tool_names)}
    for case in cases:
        scanned["case_ids"] += 1
        if any(label in case["case_id"].lower() for label in FORBIDDEN):
            findings.append({"field": "case_id", "value": case["case_id"]})
        for row in case["options"]:
            for field in ("id", "text"):
                scanned["memory_ids" if field == "id" else "memory_texts"] += 1
                value = str(row[field]).lower()
                labels = [label for label in FORBIDDEN if label in value]
                if labels:
                    findings.append({"field": field, "value": row[field], "labels": labels})
    for tool in tool_names:
        labels = [label for label in FORBIDDEN if label in tool.lower()]
        if labels:
            findings.append({"field": "tool_name", "value": tool, "labels": labels})
    return {"schema": "mf-r5-07-contamination-audit/1",
            "decision": "PASS" if not findings else "FAIL",
            "dataset": "r4-05-adversarial-cases-v1",
            "scenario_labels_checked": list(FORBIDDEN),
            "scanned_counts": scanned,
            "findings": findings,
            "input_sha256": {
                "experiments/r4_05_adversarial_cases.py": hashlib.sha256(
                    (ROOT / "experiments/r4_05_adversarial_cases.py").read_bytes()).hexdigest(),
                "tools/r5_07_contamination_audit.py": hashlib.sha256(
                    Path(__file__).read_bytes()).hexdigest(),
            },
            "limitations": ["Lexical scan only; it does not establish semantic non-leakage.",
                            "Audit covers the R4-05 synthetic fixture and its declared tool catalog."]}


def audit() -> dict[str, Any]:
    return audit_dataset(build_cases())


def main() -> int:
    out = ROOT / "research/results/r5-07-contamination-audit.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    report = audit()
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(out), "decision": report["decision"],
                      "findings": len(report["findings"]), "scanned": report["scanned_counts"]}))
    return int(report["decision"] != "PASS")


if __name__ == "__main__":
    raise SystemExit(main())

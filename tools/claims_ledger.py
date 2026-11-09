"""Validate and render the public claims-to-evidence ledger."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "research" / "claims.json"
OUT_JSON = ROOT / "research" / "results" / "CLAIMS_LEDGER.json"
OUT_MD = ROOT / "research" / "results" / "CLAIMS_LEDGER.md"
REQUIRED = {"id", "claim", "class", "source", "evidence", "dataset", "model",
            "commit_field", "verdict", "limitation", "expected_commit",
            "expected_evidence_sha256", "quantitative_assertions"}


def _at(payload: Any, path: str) -> Any:
    value = payload
    for part in path.strip("/").split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        if isinstance(value, list):
            value = value[int(part)]
        elif isinstance(value, dict):
            value = value[part]
        else:
            raise KeyError(path)
    return value


def validate_claim(raw: dict[str, Any], payload: dict[str, Any], evidence_sha256: str) -> list[str]:
    """Refuse stale run bindings and mismatched quantitative assertions."""
    issues: list[str] = []
    claim_id = raw.get("id", "<unknown>")
    observed_commit = payload.get(raw.get("commit_field", ""))
    if observed_commit != raw.get("expected_commit"):
        issues.append(f"{claim_id}: outdated or mismatched evidence commit")
    if evidence_sha256 != raw.get("expected_evidence_sha256"):
        issues.append(f"{claim_id}: evidence SHA-256 changed")
    for assertion in raw.get("quantitative_assertions", []):
        try:
            if "sum_path" in assertion:
                observed = sum(_at(payload, assertion["sum_path"]))
            elif "sum_field" in assertion:
                observed = sum(row[assertion["sum_field"]]
                               for row in _at(payload, assertion["rows_path"]))
            elif "sum_values_path" in assertion:
                observed = sum(_at(payload, assertion["sum_values_path"]).values())
            elif "count_path" in assertion:
                observed = len(_at(payload, assertion["count_path"]))
            else:
                observed = _at(payload, assertion["path"])
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            issues.append(f"{claim_id}: missing or invalid quantitative field {assertion}: {exc}")
            continue
        if observed != assertion["equals"]:
            issues.append(f"{claim_id}: assertion {assertion} observed {observed!r}")
    return issues


def build() -> dict[str, Any]:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in registry["claims"]:
        missing = REQUIRED - raw.keys()
        if missing:
            raise ValueError(f"{raw.get('id', '<unknown>')}: missing {sorted(missing)}")
        if raw["id"] in seen:
            raise ValueError(f"duplicate claim id: {raw['id']}")
        seen.add(raw["id"])
        source = ROOT / raw["source"]
        evidence = ROOT / raw["evidence"]
        if not source.is_file() or not evidence.is_file():
            raise ValueError(f"{raw['id']}: source or evidence does not exist")
        payload = json.loads(evidence.read_text(encoding="utf-8"))
        commit = payload.get(raw["commit_field"])
        if not commit:
            raise ValueError(f"{raw['id']}: evidence lacks {raw['commit_field']}")
        actual_sha = hashlib.sha256(evidence.read_bytes()).hexdigest()
        issues = validate_claim(raw, payload, actual_sha)
        if issues:
            raise ValueError("; ".join(issues))
        row = dict(raw)
        row["commit"] = commit
        row["evidence_sha256"] = actual_sha
        row["claim_status"] = "SUPPORTED"
        rows.append(row)
    return {"schema": "memory-fabric-claims-ledger/1", "generated_by": "tools/claims_ledger.py", "claims": rows}


def markdown(data: dict[str, Any]) -> str:
    lines = ["# Claims-to-evidence ledger", "", "Generated from `research/claims.json`. Every quantitative statement is bound to exact evidence bytes, the recorded run commit, and registered value/denominator assertions; a missing or changed field prevents SUPPORTED status.", "", "| ID | claim status | verdict | evidence / commit | limitation |", "|---|---|---|---|---|"]
    for row in data["claims"]:
        evidence = f"[{row['evidence']}]({'../../' + row['evidence']}) @ `{str(row['commit'])[:12]}`"
        lines.append(f"| `{row['id']}` | **{row['claim_status']}** | **{row['verdict']}** | {evidence} | {row['limitation']} |")
    return "\n".join(lines) + "\n"


def write() -> None:
    data = build()
    OUT_JSON.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    OUT_MD.write_text(markdown(data), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    result = build()
    if args.write:
        write()
    else:
        print(json.dumps(result, indent=2))

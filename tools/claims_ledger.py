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
REQUIRED = {"id", "claim", "class", "source", "evidence", "dataset", "model", "commit_field", "verdict", "limitation"}


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
        row = dict(raw)
        row["commit"] = commit
        row["evidence_sha256"] = hashlib.sha256(evidence.read_bytes()).hexdigest()
        rows.append(row)
    return {"schema": "memory-fabric-claims-ledger/1", "generated_by": "tools/claims_ledger.py", "claims": rows}


def markdown(data: dict[str, Any]) -> str:
    lines = ["# Claims-to-evidence ledger", "", "Generated from `research/claims.json`. Every row names its scope and limitation; a missing file, commit field, or required field fails generation.", "", "| ID | claim class | verdict | evidence / commit | limitation |", "|---|---|---|---|---|"]
    for row in data["claims"]:
        evidence = f"[{row['evidence']}]({'../../' + row['evidence']}) @ `{str(row['commit'])[:12]}`"
        lines.append(f"| `{row['id']}` | {row['class']} | **{row['verdict']}** | {evidence} | {row['limitation']} |")
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

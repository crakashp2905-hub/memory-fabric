"""Build a local hash inventory for every task row in the CDM ledger."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "docs" / "CDM_TASK_LEDGER.md"
OUTPUT = ROOT / "research" / "results" / "cdm" / "task-evidence-inventory.json"
PATH_RE = re.compile(r"(?<![\w.-])((?:docs|research|src|tests|benchmarks|tools)/[A-Za-z0-9_./-]+)")
MODULE_RE = re.compile(r"\b(tests|benchmarks)\.([a-zA-Z0-9_]+)\b")
FILE_RE = re.compile(r"(?:^|[\s`'(])((?:\.\./)?[A-Za-z0-9_./-]+\.(?:py|md|json|csv|html|yaml|yml|toml|txt))(?:$|[\s`'):,])")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _artifact_paths(text: str, file_index: dict[str, list[str]]) -> list[str]:
    candidates = set(PATH_RE.findall(text))
    candidates.update(FILE_RE.findall(text))
    for package, module in MODULE_RE.findall(text):
        candidates.add(f"{package}/{module}.py")
    resolved: set[str] = set()
    for candidate in candidates:
        clean = candidate.lstrip("./").rstrip(".,;:)")
        path = (ROOT / clean).resolve()
        if path.is_relative_to(ROOT) and path.is_file():
            resolved.add(path.relative_to(ROOT).as_posix())
        elif "/" not in clean and len(file_index.get(clean, ())) == 1:
            resolved.add(file_index[clean][0])
    return sorted(resolved)


def build_inventory() -> dict[str, Any]:
    lines = LEDGER.read_text(encoding="utf-8").splitlines()
    file_index: dict[str, list[str]] = {}
    for path in ROOT.rglob("*"):
        if (path.is_file() and not any(part in {".git", ".tmp", ".tmp-cdm", "__pycache__"}
                                       for part in path.relative_to(ROOT).parts)):
            file_index.setdefault(path.name, []).append(path.relative_to(ROOT).as_posix())
    section = ""
    entries: list[dict[str, Any]] = []
    for line in lines:
        if line.startswith("## Complete at this checkpoint"):
            section = "complete"
        elif line.startswith("## Partial"):
            section = "partial"
        elif line.startswith("## Open"):
            section = "open"
        match = re.match(r"^\| CDM-(\d{3}) \|(.+?)\|\s*$", line)
        if match is None:
            continue
        task_id, body = match.groups()
        artifact_paths = _artifact_paths(body, file_index)
        artifacts = []
        for relative in artifact_paths:
            artifact = ROOT / relative
            artifacts.append({"path": relative, "sha256": sha256(artifact.read_bytes())})
        entries.append({"task_id": f"CDM-{task_id}", "status": section,
            "evidence_row_sha256": sha256(line.encode("utf-8")),
            "referenced_artifacts": artifacts})
    ids = [item["task_id"] for item in entries]
    expected = {f"CDM-{number:03d}" for number in range(1, 241)}
    if len(ids) != len(set(ids)) or set(ids) != expected:
        raise ValueError("task ledger must contain each CDM-001..240 ID exactly once")
    counts = {status: sum(item["status"] == status for item in entries)
              for status in ("complete", "partial", "open")}
    return {"schema": "cdm-task-evidence-inventory-v1", "ledger": "docs/CDM_TASK_LEDGER.md",
        "task_count": len(entries), "status_counts": counts,
        "artifact_count": sum(len(item["referenced_artifacts"]) for item in entries),
        "tasks": sorted(entries, key=lambda item: item["task_id"])}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=OUTPUT)
    args = parser.parse_args()
    output = args.out.resolve()
    if not output.is_relative_to(ROOT):
        parser.error("output must stay inside the local checkout")
    inventory = build_inventory()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(inventory, indent=2, sort_keys=True) + "\n",
                      encoding="utf-8")
    print(f"PASS: inventoried {inventory['task_count']} tasks and "
          f"{inventory['artifact_count']} existing evidence artifacts at {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

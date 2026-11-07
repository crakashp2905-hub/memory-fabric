"""Generate and verify the 260-task offline qualification ledger.

The checklist is parsed as data. Completion is never inferred from keywords:
an override must name existing evidence and explicitly record acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
SCOPE = ROOT / "docs" / "MEMORY_FABRIC_OFFLINE_10_OF_10_MASTER_CHECKLIST.md"
BASE = ROOT / "research" / "offline_qualification"
OVERRIDES = BASE / "evidence.json"
REGISTER = BASE / "register.json"
REPORT = BASE / "README.md"
TASK = re.compile(
    r"^- \[ \] \*\*(?P<id>[A-Z][A-Z0-9]*-\d{2})\*\*.*?"
    r"· \*\*(?P<priority>P\d)\*\* · (?P<task>.*?) "
    r"\*\*Acceptance:\*\* (?P<acceptance>.*)\.\.$"
)
STATUSES = {"DONE", "PARTIAL", "TODO", "BLOCKED", "NOT_TESTED", "INCOMPLETE"}
LEVELS = {"NOT_TESTED", "SIMULATED", "CONTRACT", "INTERNAL_INTEGRATION",
          "EXTERNAL_INDEPENDENT"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def head() -> tuple[str, bool]:
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                         capture_output=True, text=True, check=True).stdout.strip()
    dirty = bool(subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                                capture_output=True, text=True, check=True).stdout.strip())
    return sha, dirty


def parse_scope(text: str) -> list[dict[str, str]]:
    rows = [match.groupdict() for line in text.splitlines()
            if (match := TASK.match(line))]
    ids = [row["id"] for row in rows]
    if len(rows) != 260 or len(ids) != len(set(ids)):
        raise ValueError(f"expected 260 unique tasks, found {len(rows)} / {len(set(ids))}")
    return rows


def load_overrides() -> dict[str, dict[str, Any]]:
    raw = json.loads(OVERRIDES.read_text(encoding="utf-8"))
    return {str(row["task_id"]): row for row in raw["tasks"]}


def verify_artifact(path: str) -> tuple[str | None, str | None]:
    """Return digest and parse error for one declared evidence artifact."""
    candidate = (ROOT / path).resolve()
    try:
        candidate.relative_to(ROOT.resolve())
    except ValueError:
        return None, "path escapes repository"
    if not candidate.is_file():
        return None, "file is missing"
    try:
        if candidate.suffix.lower() == ".json":
            json.loads(candidate.read_text(encoding="utf-8"))
        elif candidate.suffix.lower() == ".xml":
            ET.parse(candidate)
    except (UnicodeError, ValueError, ET.ParseError) as exc:
        return None, f"invalid {candidate.suffix.lower()} evidence: {exc}"
    return sha256(candidate), None


def build() -> dict[str, Any]:
    tasks = parse_scope(SCOPE.read_text(encoding="utf-8"))
    overrides = load_overrides()
    unknown = set(overrides) - {row["id"] for row in tasks}
    if unknown:
        raise ValueError(f"evidence names unknown tasks: {sorted(unknown)}")
    rows: list[dict[str, Any]] = []
    for task in tasks:
        evidence = overrides.get(task["id"], {})
        status = evidence.get("status", "TODO")
        level = evidence.get("evidence_level", "NOT_TESTED")
        paths = evidence.get("evidence_paths", [])
        if status not in STATUSES or level not in LEVELS:
            raise ValueError(f"{task['id']}: invalid status or evidence level")
        artifact_digests: dict[str, str] = {}
        artifact_issues: dict[str, str] = {}
        for path in paths:
            digest, issue = verify_artifact(path)
            if issue:
                artifact_issues[path] = issue
            else:
                artifact_digests[path] = str(digest)
        accepted = bool(evidence.get("acceptance_passed", False))
        if artifact_issues:
            status = "INCOMPLETE"
            accepted = False
        if status == "DONE" and (not accepted or not paths or level == "NOT_TESTED"):
            raise ValueError(f"{task['id']}: DONE requires passed acceptance and evidence")
        if status != "DONE" and accepted:
            raise ValueError(f"{task['id']}: acceptance_passed requires DONE")
        rows.append({
            "task_id": task["id"], "priority": task["priority"],
            "task": task["task"], "acceptance": task["acceptance"],
            "status": status, "acceptance_passed": accepted,
            "evidence_level": level, "evidence_paths": paths,
            "evidence_digests": artifact_digests,
            "evidence_issues": artifact_issues,
            "limitations": evidence.get("limitations", []),
        })
    commit, dirty = head()
    counts = Counter(row["status"] for row in rows)
    p0_open = [row["task_id"] for row in rows
               if row["priority"] == "P0" and row["status"] != "DONE"]
    gates = {f"G{n}": "BLOCKED" for n in range(1, 6)}
    internal = "OFFLINE-QUALIFIED" if not p0_open and all(
        value == "PASS" for value in gates.values()) else "BLOCKED"
    return {
        "schema": "memory-fabric-offline-qualification/1",
        "scope": {"path": str(SCOPE.relative_to(ROOT)).replace("\\", "/"),
                  "sha256": sha256(SCOPE), "tasks": len(rows)},
        "source": {"commit": commit, "dirty": dirty},
        "summary": {"counts": dict(sorted(counts.items())),
                    "completed": counts["DONE"],
                    "total": len(rows),
                    "percent_complete": round(100 * counts["DONE"] / len(rows), 2),
                    "p0_open": len(p0_open), "internal_status": internal},
        "gates": gates,
        "known_unverified": [
            "independent security review", "real-user pilot",
            "real-model agent evaluation", "physical multi-host validation",
            "global prior-art novelty review", "package publication approval",
        ],
        "tasks": rows,
    }


def normalized_digest(data: Mapping[str, Any]) -> str:
    normalized = dict(data)
    normalized["source"] = {"commit": "<normalized>", "dirty": False}
    payload = json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def validate_seed_outputs(declared: Sequence[int], observed: Sequence[int]) -> list[str]:
    issues: list[str] = []
    if len(observed) != len(set(observed)):
        issues.append("repeated seed output")
    missing = sorted(set(declared) - set(observed))
    extra = sorted(set(observed) - set(declared))
    if missing:
        issues.append(f"missing seeds: {missing}")
    if extra:
        issues.append(f"extra seeds: {extra}")
    return issues


def render(data: Mapping[str, Any]) -> str:
    summary = data["summary"]
    lines = ["# Offline 10/10 qualification ledger", "",
             f"Strict completion: **{summary['completed']} / {summary['total']} "
             f"({summary['percent_complete']:.2f}%)**. Internal status: "
             f"**{summary['internal_status']}**.", "",
             "A task is counted only when its exact acceptance condition has evidence. "
             "Every artifact is SHA-256 bound; malformed or missing evidence is INCOMPLETE. "
             "Existing code without acceptance evidence is PARTIAL or TODO, never DONE.", "",
             f"Normalized ledger digest: `{normalized_digest(data)}`.", "",
             "| status | count |", "|---|---:|"]
    for status in sorted(STATUSES):
        lines.append(f"| {status} | {summary['counts'].get(status, 0)} |")
    lines += ["", "## Graduation gates", "",
              "| gate | status |", "|---|---|"]
    lines += [f"| {gate} | **{status}** |" for gate, status in data["gates"].items()]
    lines += ["", "## Task ledger", "",
              "| task | priority | status | evidence level | evidence |",
              "|---|---|---|---|---|"]
    for row in data["tasks"]:
        paths = ", ".join(f"`{path}`" for path in row["evidence_paths"]) or "—"
        lines.append(f"| {row['task_id']} | {row['priority']} | {row['status']} | "
                     f"{row['evidence_level']} | {paths} |")
    return "\n".join(lines) + "\n"


def write() -> dict[str, Any]:
    data = build()
    REGISTER.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    REPORT.write_text(render(data), encoding="utf-8")
    return data


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    data = write() if args.write else build()
    print(json.dumps(data["summary"], indent=2))
    return 0 if data["summary"]["internal_status"] == "OFFLINE-QUALIFIED" else 2


if __name__ == "__main__":
    raise SystemExit(main())

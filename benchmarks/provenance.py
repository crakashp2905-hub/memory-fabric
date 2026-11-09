"""Exact source provenance for newly generated research results."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SHA = re.compile(r"^[0-9a-f]{40}$")


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True,
                          text=True).stdout.strip()


def stamp(data: dict[str, Any], *, exploratory: bool = False,
          reason: str | None = None, root: Path = ROOT) -> dict[str, Any]:
    """Return a copy bound to HEAD; refuse dirty runs without an explicit label."""
    commit = _git(root, "rev-parse", "HEAD")
    dirty = bool(_git(root, "status", "--porcelain"))
    record = dict(data)
    record["source"] = {"commit": commit, "dirty": dirty,
                        "classification": "EXPLORATORY" if exploratory else "QUALIFIED"}
    if reason:
        record["source"]["reason"] = reason
    issues = validate(record, root=root)
    if issues:
        raise ValueError("; ".join(issues))
    return record


def validate(data: dict[str, Any], *, root: Path = ROOT) -> list[str]:
    issues: list[str] = []
    source = data.get("source")
    if not isinstance(source, dict):
        return ["missing source provenance"]
    commit = source.get("commit")
    if not isinstance(commit, str) or not SHA.fullmatch(commit):
        issues.append("source commit must be an exact 40-character SHA")
    else:
        exists = subprocess.run(["git", "cat-file", "-e", f"{commit}^{{commit}}"],
                                cwd=root, capture_output=True).returncode == 0
        if not exists:
            issues.append("source commit is unknown to this repository")
    if not isinstance(source.get("dirty"), bool):
        issues.append("source dirty state must be an explicit boolean")
    if source.get("dirty") is True:
        if source.get("classification") != "EXPLORATORY" or not source.get("reason"):
            issues.append("dirty source requires explicit EXPLORATORY classification and reason")
    elif source.get("classification") not in {"QUALIFIED", "EXPLORATORY"}:
        issues.append("source classification must be QUALIFIED or EXPLORATORY")
    return issues

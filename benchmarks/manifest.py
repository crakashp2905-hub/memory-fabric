"""One run manifest schema for every suite (MF-032), with the decision outputs of §7A.12.

A manifest is written for every run, including runs that did not happen:
`NOT_RUN` and `BLOCKED` carry their reason, so a missing result is a recorded
fact rather than an absence. `validate` refuses a manifest that claims more
than it shows: a PASS without a registered baseline or a passed oracle sanity
check, a result without a commit, a cost per safe success with no safe
success.
"""

from __future__ import annotations

import json
import hashlib
import multiprocessing
import os
import platform
import sqlite3
import subprocess
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from benchmarks.provenance import stamp as stamp_source

SCHEMA = "mf-run-manifest/1"
DECISIONS = ("PASS", "FAIL", "INCONCLUSIVE", "INVALID", "NOT_RUN", "BLOCKED", "DESCRIPTIVE")
ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "research" / "results" / "bench_runs"
ENVIRONMENT_FIELDS = {"python", "os", "sqlite", "logical_cpus", "thread_count", "process_count"}


def digest_inputs(paths: list[str], *, root: Path = ROOT) -> dict[str, str]:
    """Hash declared run inputs, refusing missing paths and paths outside the checkout."""
    root = root.resolve()
    result: dict[str, str] = {}
    for raw in sorted(set(paths)):
        candidate = (root / raw).resolve()
        try:
            relative = candidate.relative_to(root).as_posix()
        except ValueError as exc:
            raise ValueError(f"input path escapes repository: {raw}") from exc
        if not candidate.is_file():
            raise ValueError(f"benchmark input is missing: {raw}")
        result[relative] = hashlib.sha256(candidate.read_bytes()).hexdigest()
    return result


def capture_environment() -> dict[str, Any]:
    """Capture runtime and host facts without timestamps or other run noise."""
    return {
        "python": platform.python_version(),
        "os": platform.platform(),
        "sqlite": sqlite3.sqlite_version,
        "logical_cpus": os.cpu_count(),
        "thread_count": threading.active_count(),
        "process_count": len(multiprocessing.active_children()) + 1,
    }


def digest(m: "Manifest | dict[str, Any]") -> str:
    """Hash manifest content while excluding explicitly nondeterministic timestamps."""
    data = m.to_json() if isinstance(m, Manifest) else dict(m)

    def stable(value: Any) -> Any:
        if isinstance(value, dict):
            return {key: stable(item) for key, item in sorted(value.items())
                    if key not in {"timestamp", "created_at", "updated_at", "built_at"}}
        if isinstance(value, list):
            return [stable(item) for item in value]
        return value

    encoded = json.dumps(stable(data), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def head() -> str:
    done = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT)
    return done.stdout.strip() if done.returncode == 0 else ""


@dataclass
class Manifest:
    run_id: str
    suite: str
    arm: str
    decision: str
    repo_commit: str = ""
    reason: str = ""
    dataset: dict[str, Any] = field(default_factory=dict)
    model: dict[str, Any] = field(default_factory=lambda: {"provider": None, "id": None})
    budget: dict[str, Any] = field(default_factory=dict)
    seeds: list[int] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=lambda: {"attempted": 0, "completed": 0, "solved": 0,
                                                             "skipped": 0, "failed": 0})
    results: dict[str, Any] = field(default_factory=dict)
    cost: dict[str, Any] = field(default_factory=dict)
    verification: dict[str, bool] = field(default_factory=lambda: {
        "baseline_registered": False, "oracle_sanity_passed": False, "holdout_frozen": False,
        "independent_replicated": False})
    environment: dict[str, Any] = field(default_factory=capture_environment)
    input_digests: dict[str, str] = field(default_factory=dict)
    prereg: str | None = None
    schema: str = SCHEMA

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


def validate(m: Manifest | dict[str, Any], *, root: Path = ROOT) -> list[str]:
    d = m.to_json() if isinstance(m, Manifest) else m
    problems = []
    if d.get("schema") != SCHEMA:
        problems.append("unknown schema")
    if d.get("decision") not in DECISIONS:
        problems.append(f"decision must be one of {DECISIONS}")
    environment = d.get("environment")
    missing_environment = ENVIRONMENT_FIELDS - set(environment or {})
    if missing_environment:
        problems.append(f"environment missing fields: {sorted(missing_environment)}")
    elif any(environment.get(key) in (None, "") for key in ENVIRONMENT_FIELDS):
        problems.append("environment fields must be populated")
    ran = d.get("decision") not in ("NOT_RUN", "BLOCKED")
    if not ran and not d.get("reason"):
        problems.append(f"{d.get('decision')} needs a reason")
    if ran and not d.get("repo_commit"):
        problems.append("a run must name the commit it ran on")
    input_digests = d.get("input_digests", {})
    if ran and not input_digests:
        problems.append("a run must digest its declared inputs")
    if input_digests:
        try:
            actual = digest_inputs(list(input_digests), root=root)
        except ValueError as exc:
            problems.append(str(exc))
        else:
            for path, expected in input_digests.items():
                if actual.get(path) != expected:
                    problems.append(f"input digest mismatch: {path}")
    if d.get("decision") == "PASS":
        v = d.get("verification", {})
        if not v.get("baseline_registered") or not v.get("oracle_sanity_passed"):
            problems.append("PASS needs a registered baseline and a passed oracle sanity check")
        if not d.get("prereg"):
            problems.append("PASS needs a preregistration")
    c = d.get("counts", {})
    if c.get("solved", 0) > c.get("attempted", 0):
        problems.append("more solved than attempted")
    cps = d.get("cost", {}).get("cost_per_safe_success")
    if cps is not None and not d.get("counts", {}).get("safe_solved", c.get("solved", 0)):
        problems.append("cost per safe success with no safe success")
    return problems


def write(m: Manifest, directory: Path = RUNS, *, root: Path = ROOT) -> Path:
    data = stamp_source(m.to_json(), root=root)
    if data.get("decision") not in ("NOT_RUN", "BLOCKED"):
        dataset = data.get("dataset", {})
        paths = list(dataset.get("input_files", []))
        if dataset.get("generator"):
            paths.append(dataset["generator"])
        data["input_digests"] = digest_inputs(paths, root=root)
    problems = validate(data)
    if problems:
        raise ValueError("; ".join(problems))
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{m.run_id}.json"
    path.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return path


def read_all(directory: Path = RUNS) -> list[dict[str, Any]]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(directory.glob("*.json"), key=lambda p: p.name)]

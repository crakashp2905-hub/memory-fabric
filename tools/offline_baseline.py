"""Read-only, deterministic offline baseline report for the current checkout."""
from __future__ import annotations

import hashlib
import importlib.metadata
import importlib.util
import json
import os
import platform
import sqlite3
import subprocess
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_ENV = {"python", "implementation", "os", "machine", "sqlite",
                "logical_cpus", "benchmark_threads", "benchmark_processes"}
INPUTS = (
    "docs/MEMORY_FABRIC_OFFLINE_10_OF_10_MASTER_CHECKLIST.md",
    "research/offline_qualification/evidence.json",
    "research/claims.json",
    "benchmarks/registry.json",
)
OPTIONAL = {
    "crypto": "cryptography", "oauth": "jwt", "postgres": "psycopg",
    "retrieval": "fastembed", "claude": "anthropic", "langchain": "langchain_core",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True,
                          capture_output=True, text=True).stdout.strip()


def build() -> dict[str, Any]:
    packages = []
    for dist in importlib.metadata.distributions():
        name = dist.metadata.get("Name")
        if name:
            packages.append({"name": name.lower(), "version": dist.version})
    packages.sort(key=lambda row: (row["name"], row["version"]))
    optional = {}
    for capability, module in OPTIONAL.items():
        available = importlib.util.find_spec(module) is not None
        optional[capability] = {
            "status": "AVAILABLE" if available else "UNAVAILABLE",
            "module": module,
            "reason": None if available else "optional dependency is not installed",
            "impact": f"{capability} acceptance arms remain NOT_TESTED" if not available else None,
        }
    return {
        "schema": "memory-fabric-offline-baseline/1",
        "source": {"commit": git("rev-parse", "HEAD"),
                   "branch": git("branch", "--show-current"),
                   "dirty": bool(git("status", "--porcelain"))},
        "environment": {
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "os": platform.platform(), "machine": platform.machine(),
            "sqlite": sqlite3.sqlite_version, "logical_cpus": os.cpu_count(),
            "benchmark_threads": 1, "benchmark_processes": 1,
        },
        "inputs": {path: digest(ROOT / path) for path in INPUTS},
        "packages": packages,
        "optional_capabilities": optional,
        "normalization": "no timestamps; sorted packages and mappings",
        "limitations": [
            "Installed packages describe this interpreter, not every supported Python version.",
            "Hardware counters and timing measurements are intentionally absent from this deterministic report.",
        ],
    }


def validate(data: Mapping[str, Any]) -> list[str]:
    issues: list[str] = []
    if data.get("schema") != "memory-fabric-offline-baseline/1":
        issues.append("unknown schema")
    missing = REQUIRED_ENV - set(data.get("environment", {}))
    if missing:
        issues.append(f"missing environment fields: {sorted(missing)}")
    source = data.get("source", {})
    commit = source.get("commit", "")
    if not isinstance(commit, str) or len(commit) != 40:
        issues.append("source commit is not an exact SHA")
    for path, expected in data.get("inputs", {}).items():
        candidate = ROOT / path
        if not candidate.is_file() or digest(candidate) != expected:
            issues.append(f"input digest mismatch: {path}")
    return issues


def main() -> int:
    data = build()
    issues = validate(data)
    print(json.dumps({**data, "validation": {"status": "PASS" if not issues else "FAIL",
                                             "issues": issues}}, indent=2,
                     sort_keys=True))
    return 0 if not issues else 2


if __name__ == "__main__":
    raise SystemExit(main())

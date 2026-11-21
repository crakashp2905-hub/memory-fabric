#!/usr/bin/env python3
"""Record the exact starting environment for agent-outcome work (checklist W01-01).

    python tools/baseline_manifest.py                       # print the manifest
    python tools/baseline_manifest.py --out PATH            # write it
    python tools/baseline_manifest.py --verify PATH         # integrity of a stored manifest
    python tools/baseline_manifest.py --compare PATH        # stored manifest vs this checkout

The manifest pins the source commit and whether the tree was clean, the Python
interpreter, the SQLite library, the operating system, the package version, the
declared dependencies and which optional distributions are installed, with their
versions. It reads only local state (git, the interpreter, `sqlite3`, `platform`,
installed distribution metadata); it makes no network call.

It is deterministic: there is no timestamp, keys are sorted, and lists are
sorted, so two runs on the same checkout and environment produce identical bytes.
`manifest_sha256` covers every other field, so a stored manifest can be checked
for tampering without re-running it on the original machine.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import sqlite3
import subprocess
import sys
import tomllib
from importlib import metadata
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_ID = "memory-fabric.baseline-manifest.v1"
_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")


def _canonical(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False).encode("utf-8")


def _git(root: Path, *args: str) -> str | None:
    try:
        done = subprocess.run(["git", *args], cwd=root, check=True, capture_output=True,
                              text=True, encoding="utf-8", errors="replace")
    except (OSError, subprocess.CalledProcessError):
        return None
    return done.stdout


def source_identity(root: Path) -> dict[str, Any]:
    commit = (_git(root, "rev-parse", "HEAD") or "").strip()
    status = _git(root, "status", "--porcelain", "--untracked-files=all")
    dirty = sorted(line[3:] for line in (status or "").splitlines() if line.strip())
    return {
        "commit_sha": commit if re.fullmatch(r"[0-9a-f]{40}", commit) else None,
        "tree_clean": status is not None and not dirty,
        "dirty_paths": dirty[:50],
        "dirty_path_count": len(dirty),
    }


def _requirement_name(spec: str) -> str:
    match = _NAME.match(spec)
    if match is None:
        raise ValueError(f"unparseable requirement {spec!r}")
    return re.sub(r"[-_.]+", "-", match.group(1)).lower()


def _installed(name: str) -> str | None:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None


def build(root: Path = ROOT) -> dict[str, Any]:
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    declared = sorted(project.get("dependencies", []))
    optional = {extra: sorted(specs)
                for extra, specs in sorted(project.get("optional-dependencies", {}).items())}
    names = sorted({_requirement_name(spec)
                    for specs in [declared, *optional.values()] for spec in specs})
    body: dict[str, Any] = {
        "schema_id": SCHEMA_ID,
        "source": source_identity(root),
        "package": {"name": project["name"], "version": project["version"],
                    "requires_python": project.get("requires-python")},
        "python": {"implementation": platform.python_implementation(),
                   "version": platform.python_version()},
        "sqlite": {"library_version": sqlite3.sqlite_version},
        "os": {"system": platform.system(), "release": platform.release(),
               "machine": platform.machine()},
        "dependencies": {"runtime": declared, "optional": optional},
        "installed_distributions": {name: _installed(name) for name in names},
        "network_calls": 0,
    }
    body["manifest_sha256"] = hashlib.sha256(_canonical(body)).hexdigest()
    return body


def render(manifest: dict[str, Any]) -> str:
    return json.dumps(manifest, sort_keys=True, indent=2, ensure_ascii=True) + "\n"


def verify(manifest: dict[str, Any]) -> list[str]:
    """Integrity problems in a stored manifest; empty when it is intact."""
    problems: list[str] = []
    if manifest.get("schema_id") != SCHEMA_ID:
        problems.append("unsupported schema_id")
    stated = manifest.get("manifest_sha256")
    body = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    if stated != hashlib.sha256(_canonical(body)).hexdigest():
        problems.append("manifest_sha256 does not match the manifest body")
    source = manifest.get("source", {})
    if not isinstance(source.get("commit_sha"), str) or not re.fullmatch(
            r"[0-9a-f]{40}", source.get("commit_sha") or ""):
        problems.append("source.commit_sha is not a 40-hex commit")
    return problems


def compare(stored: dict[str, Any], current: dict[str, Any]) -> list[str]:
    """Fields where this checkout and environment differ from the stored baseline."""
    differences = []
    for key in sorted(set(stored) | set(current)):
        if key == "manifest_sha256":
            continue
        if stored.get(key) != current.get(key):
            differences.append(key)
    return differences


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--verify", type=Path)
    parser.add_argument("--compare", type=Path)
    args = parser.parse_args(argv)
    if args.verify is not None:
        problems = verify(json.loads(args.verify.read_text(encoding="utf-8")))
        print("PASS" if not problems else "FAIL\n" + "\n".join(f"  - {p}" for p in problems))
        return 1 if problems else 0
    current = build(args.root)
    if args.compare is not None:
        differences = compare(json.loads(args.compare.read_text(encoding="utf-8")), current)
        print("IDENTICAL" if not differences else "DIFFERS: " + ", ".join(differences))
        return 1 if differences else 0
    text = render(current)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

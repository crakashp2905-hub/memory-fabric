"""Inspect built wheel/sdist contents for secrets and undeclared assets."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))
from memory_fabric.governance.sensitive import SensitiveDataDetector  # noqa: E402
from scan_secrets import ALLOWED_SNIPPETS, is_allowed  # noqa: E402

TEXT_SUFFIXES = {".py", ".pyi", ".json", ".html", ".txt", ".md", ".toml",
                 ".cfg", ".in", ".typed"}
TEXT_BASENAMES = {"LICENSE", "WHEEL", "METADATA", "RECORD", "PKG-INFO"}
SDIST_ROOT_FILES = {"LICENSE", "MANIFEST.in", "README.md", "PKG-INFO",
                    "pyproject.toml", "setup.cfg"}
SDIST_META_FILES = {"PKG-INFO", "SOURCES.txt", "dependency_links.txt", "entry_points.txt",
                    "requires.txt", "top_level.txt"}


def allowed_member(name: str, kind: str) -> bool:
    parts = Path(name).as_posix().split("/")
    if any(part.lower() in {"test", "tests", "fixture", "fixtures", "corpus",
                            "corpora", "benchmark", "benchmarks", "research"}
           for part in parts):
        return False
    suffix = Path(name).suffix.lower()
    if kind == "wheel":
        return ((len(parts) >= 2 and parts[0] == "memory_fabric"
                 and (suffix in TEXT_SUFFIXES or parts[-1] == "py.typed"))
                or (len(parts) >= 2 and parts[0].endswith(".dist-info")
                    and parts[-1] in {"METADATA", "WHEEL", "RECORD", "top_level.txt",
                                      "entry_points.txt", "LICENSE"}))
    if kind == "sdist":
        if len(parts) < 2 or not parts[0].startswith("memory_fabric-"):
            return False
        rel = parts[1:]
        if len(rel) == 1 and rel[0] in SDIST_ROOT_FILES:
            return True
        if rel[0] == "src" and len(rel) >= 3 and rel[1] == "memory_fabric":
            return suffix in TEXT_SUFFIXES or rel[-1] == "py.typed"
        return (len(rel) >= 2 and rel[0] == "src" and rel[1].endswith(".egg-info")
                and len(rel) == 3 and rel[2] in SDIST_META_FILES)
    return False


def audit_members(members: Iterable[tuple[str, bytes]], kind: str) -> list[dict[str, object]]:
    detector = SensitiveDataDetector(check_entropy=False)
    issues: list[dict[str, object]] = []
    for name, data in members:
        normalized = Path(name).as_posix()
        if not allowed_member(normalized, kind):
            issues.append({"member": normalized, "kind": "unexpected-member"})
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            issues.append({"member": normalized, "kind": "unexpected-binary"})
            continue
        if (Path(normalized).suffix.lower() not in TEXT_SUFFIXES
                and Path(normalized).name not in TEXT_BASENAMES
                and not normalized.endswith("py.typed")):
            issues.append({"member": normalized, "kind": "unapproved-file-type"})
            continue
        source_path = normalized
        if kind == "wheel" and source_path.startswith("memory_fabric/"):
            source_path = "src/" + source_path
        elif kind == "sdist":
            prefix, _, source_path = source_path.partition("/")
            if source_path.startswith("src/"):
                pass
            elif source_path == "README.md":
                source_path = "README.md"
        for finding in detector.scan(text):
            if finding.severity != "high":
                continue
            raw = text[finding.start:finding.end]
            line = text[:finding.start].count("\n") + 1
            line_text = text.splitlines()[line - 1] if line <= len(text.splitlines()) else ""
            narrow_exception = any(path == source_path and kind_name == finding.kind
                                   and snippet in line_text
                                   for path, kind_name, snippet
                                   in ALLOWED_SNIPPETS)
            if not is_allowed(source_path, finding.kind, raw, line_text) and not narrow_exception:
                issues.append({"member": normalized, "kind": "secret-finding",
                               "rule": finding.kind, "line": line})
    return issues


def read_archive(path: Path) -> tuple[str, list[tuple[str, bytes]]]:
    if path.suffix == ".whl":
        with zipfile.ZipFile(path) as archive:
            return "wheel", [(info.filename, archive.read(info)) for info in archive.infolist()
                              if not info.is_dir()]
    if path.name.endswith((".tar.gz", ".tgz")):
        with tarfile.open(path, "r:gz") as archive:
            members = [(info.name, archive.extractfile(info).read()) for info in archive.getmembers()
                       if info.isfile() and archive.extractfile(info) is not None]
        return "sdist", members
    raise ValueError(f"unsupported distribution artifact: {path}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifacts", nargs="+", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    reports = []
    for artifact in args.artifacts:
        kind, members = read_archive(artifact)
        issues = audit_members(members, kind)
        reports.append({"artifact": artifact.name, "kind": kind,
                        "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
                        "member_count": len(members), "issue_count": len(issues),
                        "issues": issues})
    source_commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                   capture_output=True, text=True, check=True).stdout.strip()
    payload = {"schema": "memory-fabric-package-asset-audit/1",
               "source_commit": source_commit,
               "build_command": "python -m build --no-isolation",
               "artifacts": reports,
               "passed": all(report["issue_count"] == 0 for report in reports)}
    encoded = json.dumps(payload, indent=2) + "\n"
    if args.output:
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Write a local dependency/build provenance inventory; this is not a lockfile."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> int:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    inventory_commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                      capture_output=True, text=True, check=True).stdout.strip()
    dirty = bool(subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                                capture_output=True, text=True, check=True).stdout.strip())
    package_inputs_dirty = bool(subprocess.run(
        ["git", "status", "--porcelain", "--", "pyproject.toml", "README.md", "LICENSE", "src"],
        cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip())
    distributions = sorted({name.lower().replace("_", "-") for values in
                            [project.get("dependencies", [])] +
                            list(project.get("optional-dependencies", {}).values())
                            for value in values for name in [value.split("[", 1)[0].split(">", 1)[0]
                                                             .split("<", 1)[0].split("=", 1)[0]]})
    installed = {name: importlib.metadata.version(name)
                 for name in distributions
                 if _has_distribution(name)}
    repeatability_path = ROOT / "research" / "results" / "h5-01-core-build-repeatability.json"
    repeatability = (json.loads(repeatability_path.read_text(encoding="utf-8"))
                     if repeatability_path.is_file() else None)
    build_source = repeatability.get("source_commit") if repeatability else inventory_commit
    artifacts = []
    for folder in (ROOT / "dist", ROOT / ".artifacts"):
        if folder.is_dir():
            for path in sorted(folder.iterdir()):
                if not path.is_file():
                    continue
                item = {"path": path.relative_to(ROOT).as_posix(),
                        "sha256": digest(path), "bytes": path.stat().st_size,
                        "source_commit": build_source}
                if path.suffix == ".whl":
                    with zipfile.ZipFile(path) as archive:
                        names = archive.namelist()
                        metadata_name = next((name for name in names
                                              if name.endswith(".dist-info/METADATA")), None)
                        metadata = (archive.read(metadata_name).decode("utf-8")
                                    if metadata_name else "")
                    item["package_manifest"] = {
                        "file_count": len(names),
                        "requires_dist": [line.removeprefix("Requires-Dist: ")
                                          for line in metadata.splitlines()
                                          if line.startswith("Requires-Dist:")],
                    }
                artifacts.append(item)
    payload = {
        "schema": "mf-dependency-provenance/1",
        "source": {"inventory_commit": inventory_commit,
                   "build_source_commit": build_source,
                   "worktree_dirty": dirty,
                   "package_inputs_dirty": package_inputs_dirty},
        "python": sys.version,
        "project": {"name": project["name"], "version": project["version"],
                    "requires_python": project.get("requires-python"),
                    "core_dependencies": project.get("dependencies", []),
                    "optional_dependencies": project.get("optional-dependencies", {})},
        "declared_distributions": distributions,
        "installed_declared_distributions": installed,
        "artifacts": artifacts,
        "lock_metadata": {
            "status": "BLOCKED",
            "lock_file": None,
            "offline_resolution": {
                "tool": "uv 0.11.16", "command": "uv lock --offline",
                "status": "FAILED",
                "reason": "The local cache lacks pytest==9.0.3 metadata; registry access is unavailable offline.",
            },
            "note": "Installed optional packages are inventoried but do not establish a complete transitive lock.",
        },
        "build": {
            "instructions": "docs/REPRODUCIBLE_CORE_BUILD.md",
            "repeatability_result": (repeatability_path.relative_to(ROOT).as_posix()
                                     if repeatability else None),
            "repeatability": repeatability,
            "scope": "Core wheel only; optional extras are not locked and the sdist repeatability check failed.",
        },
        "inventory_run": {
            "generated_at_commit": inventory_commit,
            "worktree_dirty": dirty,
            "package_inputs_dirty": package_inputs_dirty,
            "generator_sha256": digest(Path(__file__)),
            "input_sha256": {
                path: digest(ROOT / path)
                for path in ("pyproject.toml", "README.md", "LICENSE")
            },
            "build_repeatability_sha256": (digest(repeatability_path)
                                            if repeatability else None),
        },
    }
    target = ROOT / "research" / "results" / "h5-01-dependency-provenance.json"
    target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(target.relative_to(ROOT), len(distributions), "declared distributions")
    return 0


def _has_distribution(name: str) -> bool:
    try:
        importlib.metadata.version(name)
        return True
    except importlib.metadata.PackageNotFoundError:
        return False


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

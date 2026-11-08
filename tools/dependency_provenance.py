"""Write a local dependency/build provenance inventory; this is not a lockfile."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import subprocess
import sys
import tomllib
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
    source = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                            capture_output=True, text=True, check=True).stdout.strip()
    dirty = bool(subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                                capture_output=True, text=True, check=True).stdout.strip())
    distributions = sorted({name.lower().replace("_", "-") for values in
                            [project.get("dependencies", [])] +
                            list(project.get("optional-dependencies", {}).values())
                            for value in values for name in [value.split("[", 1)[0].split(">", 1)[0]
                                                             .split("<", 1)[0].split("=", 1)[0]]})
    installed = {name: importlib.metadata.version(name)
                 for name in distributions
                 if _has_distribution(name)}
    artifacts = []
    for folder in (ROOT / "dist", ROOT / ".artifacts"):
        if folder.is_dir():
            artifacts.extend({"path": path.relative_to(ROOT).as_posix(),
                              "sha256": digest(path), "bytes": path.stat().st_size}
                             for path in sorted(folder.iterdir()) if path.is_file())
    payload = {
        "schema": "mf-dependency-provenance/1",
        "source": {"commit": source, "dirty": dirty},
        "python": sys.version,
        "project": {"name": project["name"], "version": project["version"],
                    "requires_python": project.get("requires-python"),
                    "core_dependencies": project.get("dependencies", []),
                    "optional_dependencies": project.get("optional-dependencies", {})},
        "declared_distributions": distributions,
        "installed_declared_distributions": installed,
        "artifacts": artifacts,
        "lock_metadata": "UNAVAILABLE: no committed dependency lock file",
        "reproducible_build": "NOT_ESTABLISHED: local installed versions and artifact hashes are inventory only",
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

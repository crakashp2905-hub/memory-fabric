"""Report which supported Python interpreters are locally installed and smoke tested."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from shutil import which

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research" / "results" / "p5-03-python-compatibility.json"
VERSIONS = ("3.11", "3.12", "3.13")


def interpreter_for(version: str) -> str | None:
    current = sys.version_info
    if f"{current.major}.{current.minor}" == version:
        return sys.executable
    configured = os.environ.get("MEMORY_FABRIC_PYTHON_" + version.replace(".", ""))
    if configured and Path(configured).is_file():
        return configured
    for name in (f"python{version}", f"python{version.replace('.', '')}"):
        candidate = which(name)
        if candidate:
            return candidate
    for candidate in sorted((ROOT / ".uv-python").glob(
            f"cpython-{version}*-windows-*/python.exe")):
        if candidate.is_file():
            return str(candidate)
    return None


def main() -> int:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    rows = []
    for version in VERSIONS:
        executable = interpreter_for(version)
        if executable is None:
            rows.append({"version": version, "status": "NOT_TESTED",
                         "reason": "No interpreter binary for this version is installed or discoverable."})
            continue
        proc = subprocess.run(
            [executable, "-c", "import sys, memory_fabric; print(sys.version.split()[0])"],
            cwd=ROOT, env=env, capture_output=True, text=True, check=False,
        )
        rows.append({"version": version, "status": "SMOKE_PASS" if proc.returncode == 0 else "FAIL",
                     "executable": executable, "observed_version": proc.stdout.strip(),
                     "return_code": proc.returncode, "stderr": proc.stderr[-1000:]})
    report = {
        "schema": "mf-python-compatibility-availability/1",
        "source_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                         capture_output=True, text=True, check=True).stdout.strip(),
        "supported_versions": list(VERSIONS),
        "results": rows,
        "all_interpreters_smoke_confirmed": all(
            row["status"] == "SMOKE_PASS" for row in rows),
        "limitations": [
            "A smoke import does not establish full test-suite compatibility.",
            "NOT_TESTED versions require CI or a machine with those interpreter binaries.",
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 1 if any(row["status"] == "FAIL" for row in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())

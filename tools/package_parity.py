"""Build the sdist and wheel, then run the same installed-package smoke on each.

    python tools/package_parity.py --report research/results/package-parity.json

All builds, virtual environments and invocations run in a scratch directory
under the checkout. The examples execute from that directory with checkout
paths removed from Python's environment.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import venv
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _run(command: list[str], *, cwd: Path, record: list[dict[str, Any]]) -> subprocess.CompletedProcess[str]:
    env = {key: value for key, value in os.environ.items()
           if key not in {"PYTHONPATH", "PYTHONHOME"}}
    done = subprocess.run(command, cwd=cwd, env=env, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    record.append({"command": command, "cwd": str(cwd), "exit_code": done.returncode,
                   "output_tail": done.stdout[-4000:]})
    if done.returncode:
        raise RuntimeError(f"command failed ({done.returncode}): {' '.join(command)}")
    return done


def _smoke(artifact: Path, kind: str, work: Path,
           commands: list[dict[str, Any]]) -> dict[str, Any]:
    root = work / kind
    root.mkdir()
    envdir = root / "venv"
    venv.EnvBuilder(with_pip=True, system_site_packages=True).create(envdir)
    bindir = envdir / ("Scripts" if os.name == "nt" else "bin")
    python = bindir / ("python.exe" if os.name == "nt" else "python")
    cli = bindir / ("memory-fabric.exe" if os.name == "nt" else "memory-fabric")
    _run([str(python), "-m", "pip", "install", "--quiet", "--no-deps",
          "--no-build-isolation", str(artifact)], cwd=root, record=commands)
    probe = _run([str(python), "-c",
                  "import importlib.metadata,json,memory_fabric,pathlib; "
                  "print(json.dumps({'version':importlib.metadata.version('memory-fabric'),"
                  "'module':str(pathlib.Path(memory_fabric.__file__).resolve())}))"],
                 cwd=root, record=commands)
    import_info = json.loads(probe.stdout)
    module_path = Path(import_info["module"]).resolve()
    if ROOT == module_path or ROOT in module_path.parents:
        raise RuntimeError(f"installed import came from checkout: {module_path}")
    purelib = Path(_run([str(python), "-c",
                         "import sysconfig; print(sysconfig.get_path('purelib'))"],
                        cwd=root, record=commands).stdout.strip()).resolve()
    if purelib not in module_path.parents:
        raise RuntimeError(f"installed import is outside the artifact venv: {module_path}")
    _run([str(cli), "--help"], cwd=root, record=commands)
    for example in ("quickstart.py", "reference_agent.py"):
        shutil.copy2(ROOT / "examples" / example, root / example)
    _run([str(python), str(root / "quickstart.py"), str(root / "quickstart.db")],
         cwd=root, record=commands)
    _run([str(python), str(root / "reference_agent.py")], cwd=root, record=commands)
    store = root / "initialized-store"
    _run([str(cli), "init", str(store)], cwd=root, record=commands)
    _run([str(cli), "--db", str(store / "store.db"), "--keys",
          str(store / "keys"), "doctor"], cwd=root, record=commands)
    return {"version": import_info["version"], "module_path": str(module_path),
            "checks": {"import_outside_checkout": True, "cli_help": True,
                       "quickstart": True, "reference_agent": True,
                       "init": True, "doctor": True}}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report_path = args.report if args.report.is_absolute() else ROOT / args.report
    report_path.parent.mkdir(parents=True, exist_ok=True)
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                            capture_output=True, text=True, check=True).stdout.strip()
    dirty = bool(subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                                capture_output=True, text=True, check=True).stdout.strip())
    report: dict[str, Any] = {
        "schema": "memory-fabric-package-parity/1", "source_commit": commit,
        "source_dirty_at_start": dirty, "recorded_at_utc": time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "python": sys.version, "platform": sys.platform, "artifacts": {},
        "commands": [], "passed": False,
    }
    try:
        scratch_root = ROOT / ".test-tmp"
        scratch_root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="mf-package-parity-", dir=scratch_root) as scratch:
            work = Path(scratch)
            system_temp = work / "system-temp"
            system_temp.mkdir()
            os.environ.update({"TEMP": str(system_temp), "TMP": str(system_temp),
                               "TMPDIR": str(system_temp)})
            dist = work / "dist"
            dist.mkdir()
            _run([sys.executable, "-m", "build", "--sdist", "--wheel",
                  "--no-isolation", "--outdir", str(dist)], cwd=ROOT,
                 record=report["commands"])
            artifacts = {"wheel": next(dist.glob("*.whl")),
                         "sdist": next(dist.glob("*.tar.gz"))}
            for kind, artifact in artifacts.items():
                report["artifacts"][kind] = {"filename": artifact.name,
                                              "sha256": sha256(artifact)}
                report["artifacts"][kind].update(_smoke(
                    artifact, kind, work, report["commands"]))
        wheel = report["artifacts"]["wheel"]["checks"]
        sdist = report["artifacts"]["sdist"]["checks"]
        report["parity"] = {"same_version": report["artifacts"]["wheel"]["version"]
                             == report["artifacts"]["sdist"]["version"],
                            "same_smoke_checks": wheel == sdist}
        report["passed"] = all(report["parity"].values())
    except Exception as exc:  # keep machine-readable failure evidence
        report["error"] = f"{type(exc).__name__}: {exc}"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "report": str(report_path),
                      "artifacts": report["artifacts"], "error": report.get("error")}, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

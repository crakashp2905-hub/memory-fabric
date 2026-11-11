"""Run the versioned, offline outcome-agent qualification gate.

The report distinguishes a passing scripted gate from model and deployment
evidence. Checks are defined in the adjacent immutable JSON manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = Path(__file__).with_name("agent_outcome_gate_manifest.v15.json")
MANIFEST_SCHEMA = "memory-fabric.agent-outcome-gate.v15"


def read_manifest(path: Path = MANIFEST_PATH) -> tuple[dict[str, Any], str]:
    """Load and validate the checked-in manifest and return its content digest."""
    payload = path.read_bytes()
    manifest = json.loads(payload)
    if (manifest.get("schema_id") != MANIFEST_SCHEMA
            or manifest.get("manifest_version") != 15
            or not isinstance(manifest.get("checks"), list)):
        raise ValueError("unsupported or malformed agent outcome gate manifest")
    ids = [item.get("id") for item in manifest["checks"]]
    if len(ids) != len(set(ids)) or any(not isinstance(item, str) for item in ids):
        raise ValueError("manifest check ids must be unique strings")
    return manifest, hashlib.sha256(payload).hexdigest()


def overall_status(results: list[dict[str, Any]]) -> str:
    """Return the strict aggregate status for required scripted checks."""
    required = [result for result in results if result["required_for_scripted_qualification"]]
    if any(result["status"] == "FAIL" for result in required):
        return "FAIL"
    if any(result["status"] != "PASS" for result in required):
        return "NOT_RUN"
    return "SCRIPTED_QUALIFIED"


def _module_available(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


def _run_check(check: dict[str, Any], *, timeout_s: int, run_full: bool) -> dict[str, Any]:
    check_id = check["id"]
    command = check.get("command")
    result = {"id": check_id,
              "required_for_scripted_qualification": bool(
                  check.get("required_for_scripted_qualification", False))}
    if command is None:
        return {**result, "status": "NOT_RUN", "reason": "requires separate real-world evidence"}
    if not isinstance(command, list) or not command:
        return {**result, "status": "FAIL", "reason": "invalid command in manifest"}
    if check_id == "full_repository" and not run_full:
        return {**result, "status": "NOT_RUN", "reason": "disabled by --skip-full"}
    if len(command) >= 3 and command[1] == "-m" and not _module_available(command[2]):
        return {**result, "status": "NOT_RUN", "reason": f"optional tool unavailable: {command[2]}"}
    executable = sys.executable if command[0] == "python" else command[0]
    try:
        completed = subprocess.run([executable, *command[1:]], cwd=ROOT,
                                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, timeout=timeout_s, check=False)
    except subprocess.TimeoutExpired:
        return {**result, "status": "FAIL", "reason": f"timed out after {timeout_s}s"}
    except OSError as exc:
        return {**result, "status": "FAIL", "reason": type(exc).__name__}
    if completed.returncode == 0:
        return {**result, "status": "PASS"}
    return {**result, "status": "FAIL", "reason": f"exit code {completed.returncode}"}


def build_report(*, skip_full: bool = False, timeout_s: int = 3600) -> dict[str, Any]:
    """Run manifest checks and return a content-safe evidence report."""
    manifest, manifest_sha256 = read_manifest()
    results = [_run_check(check, timeout_s=timeout_s, run_full=not skip_full)
               for check in manifest["checks"]]
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, text=True, check=False)
    dirty = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                           stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                           stderr=subprocess.DEVNULL, text=True, check=False)
    status = overall_status(results)
    return {
        "schema_id": MANIFEST_SCHEMA,
        "manifest_version": manifest["manifest_version"],
        "manifest_sha256": manifest_sha256,
        "candidate_sha": commit.stdout.strip() if commit.returncode == 0 else None,
        "working_tree_dirty": bool(dirty.stdout.strip()) if dirty.returncode == 0 else None,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "evidence_levels": {
            "scripted": status,
            "local_model": "NOT_RUN",
            "deployment": "NOT_RUN",
        },
        "checks": results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-full", action="store_true",
                        help="mark the full repository suite NOT_RUN")
    parser.add_argument("--timeout", type=int, default=3600,
                        help="per-check timeout in seconds (default: 3600)")
    parser.add_argument("--out", help="write JSON report to this path instead of stdout")
    args = parser.parse_args(argv)
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    report = json.dumps(build_report(skip_full=args.skip_full, timeout_s=args.timeout),
                        sort_keys=True, separators=(",", ":"), allow_nan=False)
    if args.out:
        Path(args.out).write_text(report + "\n", encoding="utf-8")
    else:
        sys.stdout.write(report + "\n")
    status = json.loads(report)["status"]
    return {"SCRIPTED_QUALIFIED": 0, "FAIL": 1, "NOT_RUN": 2}[status]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

#!/usr/bin/env python3
"""Run the immutable offline agent-outcome gate manifest and emit JSON status."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


SCHEMA_ID = "memory-fabric.agent-outcome-gate-manifest.v1"
REPORT_SCHEMA_ID = "memory-fabric.agent-outcome-gate-report.v1"
MANIFEST_NAME = "agent_outcome_gate_manifest.v1.json"
_STATUSES = {"PASS", "FAIL", "NOT_RUN"}


def load_manifest(path: Path) -> tuple[dict[str, Any], str]:
    raw_bytes = path.read_bytes()
    digest = hashlib.sha256(raw_bytes).hexdigest()
    try:
        manifest = json.loads(raw_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("gate manifest must be valid UTF-8 JSON") from exc
    if not isinstance(manifest, dict) or set(manifest) != {
        "schema_id", "manifest_version", "immutable", "conditions",
    }:
        raise ValueError("gate manifest fields do not match schema v1")
    if (manifest["schema_id"] != SCHEMA_ID or manifest["manifest_version"] != 1
            or manifest["immutable"] is not True):
        raise ValueError("unsupported or mutable gate manifest")
    conditions = manifest["conditions"]
    if not isinstance(conditions, list) or not conditions:
        raise ValueError("manifest must contain conditions")
    identifiers: set[str] = set()
    for condition in conditions:
        if not isinstance(condition, dict):
            raise ValueError("manifest conditions must be objects")
        if set(condition) not in (
            {"id", "required", "command"},
            {"id", "required", "status", "reason"},
        ):
            raise ValueError("condition fields do not match the manifest schema")
        condition_id = condition["id"]
        if not isinstance(condition_id, str) or not condition_id or condition_id in identifiers:
            raise ValueError("condition IDs must be unique non-empty strings")
        identifiers.add(condition_id)
        if type(condition["required"]) is not bool:
            raise ValueError("condition required flag must be boolean")
        if "command" in condition:
            command = condition["command"]
            if (not isinstance(command, list) or not command
                    or not all(isinstance(part, str) and part for part in command)):
                raise ValueError("condition command must be a non-empty argv list")
        elif condition["status"] not in _STATUSES or condition["status"] == "PASS":
            raise ValueError("static conditions may be FAIL or NOT_RUN, never predeclared PASS")
    if "real_agent_execution" not in identifiers:
        raise ValueError("manifest must report the real_agent_execution condition")
    real_agent = next(
        item for item in conditions if item["id"] == "real_agent_execution"
    )
    if real_agent.get("required") is not True:
        raise ValueError("real_agent_execution must remain a required gate condition")
    return manifest, digest


def overall_status(results: list[dict[str, Any]]) -> str:
    required = [item for item in results if item["required"]]
    if any(item["status"] == "FAIL" for item in required):
        return "FAIL"
    if any(item["status"] == "NOT_RUN" for item in required):
        return "NOT_RUN"
    return "PASS"


def run_gate(root: Path, manifest_path: Path) -> dict[str, Any]:
    manifest, manifest_digest = load_manifest(manifest_path)
    results: list[dict[str, Any]] = []
    for condition in manifest["conditions"]:
        result = {"id": condition["id"], "required": condition["required"]}
        if "status" in condition:
            result.update(status=condition["status"], reason=condition["reason"])
        else:
            try:
                completed = subprocess.run(
                    condition["command"], cwd=root, check=False,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, encoding="utf-8", errors="replace",
                )
            except OSError as exc:
                result.update(status="FAIL", exit_code=None, output=f"{type(exc).__name__}: {exc}")
            else:
                result.update(
                    status="PASS" if completed.returncode == 0 else "FAIL",
                    exit_code=completed.returncode,
                    output=completed.stdout[-4000:],
                )
        results.append(result)
    return {
        "schema_id": REPORT_SCHEMA_ID,
        "manifest_schema_id": manifest["schema_id"],
        "manifest_version": manifest["manifest_version"],
        "manifest_sha256": manifest_digest,
        "status": overall_status(results),
        "conditions": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, help="versioned gate manifest path")
    parser.add_argument("--json-out", type=Path, help="optional report destination")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    manifest_path = args.manifest or (Path(__file__).resolve().parent / MANIFEST_NAME)
    try:
        report = run_gate(root, manifest_path)
    except (OSError, ValueError) as exc:
        print(json.dumps({"schema_id": REPORT_SCHEMA_ID, "status": "FAIL",
                          "error": f"{type(exc).__name__}: {exc}"},
                         sort_keys=True, separators=(",", ":")))
        return 1
    rendered = json.dumps(report, sort_keys=True, separators=(",", ":"))
    print(rendered)
    if args.json_out is not None:
        args.json_out.write_text(rendered + "\n", encoding="utf-8")
    return 1 if report["status"] == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())

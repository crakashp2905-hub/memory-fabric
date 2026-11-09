"""Validate the internal security findings register and emit a scoped gate."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REGISTER = ROOT / "research" / "security" / "internal_findings.json"
RESULT = ROOT / "research" / "results" / "h5-10-internal-security-findings.json"
SEVERITIES = {"critical", "high", "medium", "low", "external"}
STATUSES = {"open", "fixed", "accepted", "external_required"}


def evaluate(register: dict[str, Any], root: Path = ROOT) -> dict[str, Any]:
    if register.get("schema") != "memory-fabric-internal-security-findings/1":
        raise ValueError("unsupported findings register schema")
    findings = register.get("findings")
    if not isinstance(findings, list) or not findings:
        raise ValueError("findings must be a non-empty list")
    ids: set[str] = set()
    blockers: list[str] = []
    invalid: list[str] = []
    for finding in findings:
        fid = finding.get("id")
        if not isinstance(fid, str) or not fid or fid in ids:
            raise ValueError(f"missing or duplicate finding id: {fid!r}")
        ids.add(fid)
        severity, status = finding.get("severity"), finding.get("status")
        if severity not in SEVERITIES or status not in STATUSES:
            raise ValueError(f"{fid}: invalid severity or status")
        if not finding.get("exploit_preconditions") or not finding.get("verified_fix"):
            raise ValueError(f"{fid}: exploit_preconditions and verified_fix are required")
        tests = finding.get("verification_tests")
        if not isinstance(tests, list):
            raise ValueError(f"{fid}: verification_tests must be a list")
        if status == "fixed":
            if not tests:
                raise ValueError(f"{fid}: fixed finding requires verification tests")
            for test in tests:
                rel = test.split("::", 1)[0]
                if not (root / rel).is_file():
                    invalid.append(f"{fid}: missing verification test {test}")
        if severity in {"critical", "high"} and status != "fixed":
            blockers.append(fid)
        if severity in {"critical", "high"} and status == "fixed" and finding.get("limitations"):
            blockers.append(fid)
    if invalid:
        blockers.extend(invalid)
    external = [f["id"] for f in findings if f["status"] == "external_required"]
    return {
        "schema": "memory-fabric-local-security-gate/1",
        "scope": "known findings in the checked-in internal register; this is not a security certification",
        "local_ready": not blockers,
        "blocking_findings": sorted(set(blockers)),
        "external_review_required": external,
        "external_review_complete": False,
        "findings_count": len(findings),
        "limitations": [
            "An independent external security review remains required; it cannot be completed by this local gate.",
            "Only findings present in the register are evaluated; absence is not proof of absence.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--register", type=Path, default=REGISTER)
    parser.add_argument("--output", type=Path, default=RESULT)
    args = parser.parse_args()
    data = json.loads(args.register.read_text(encoding="utf-8"))
    result = evaluate(data, ROOT)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["local_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

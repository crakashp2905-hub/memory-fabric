"""Fresh-governance versus stale-capture local ablation fixtures."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from memory_fabric import MemoryFabric
from memory_fabric.causal_replay.capture import capture
from memory_fabric.causal_replay.types import Erased, ReplayContext, Unauthorized
from memory_fabric.service import MemoryService


def _case(name: str) -> dict[str, Any]:
    fabric = MemoryFabric(":memory:", auto_activate=True)
    try:
        service = MemoryService(fabric)
        service.register_agent("owner", b"local-owner-key", tenant_id="tenant-owner")
        owner = service.session(service.issue("owner"))
        memory_id = owner.remember("synthetic private capture fixture")
        context = ReplayContext(fabric.log.head_seq)
        cached = capture(fabric, owner, [memory_id], context=context)
        expected = name == "currently_authorized"
        request_session = owner
        if name == "revoked":
            service.revoke(owner.credential)
        elif name == "erased":
            fabric.erase_content(memory_id, actor="owner", reason="local ablation fixture")
        elif name == "cross_tenant":
            service.register_agent("other", b"local-other-key", tenant_id="tenant-other")
            request_session = service.session(service.issue("other"))
        elif name != "currently_authorized":
            raise ValueError("unknown governance-ablation case")

        try:
            capture(fabric, request_session, [memory_id], context=context)
            governed_accepts = True
        except (Erased, Unauthorized):
            governed_accepts = False

        # Intentionally weaker comparator: consume a previously authorized
        # snapshot without checking current principal, tenant or erasure state.
        weak_accepts = cached.complete
        denied = not expected
        return {"case": name, "expected_accept": expected,
            "governed_accepts": governed_accepts,
            "weak_stale_snapshot_accepts": weak_accepts,
            "governed_metadata_exposed": int(denied and governed_accepts),
            "weak_metadata_exposed": (len(cached.evidence) if denied and weak_accepts else 0)}
    finally:
        fabric.close()


def run() -> dict[str, Any]:
    rows = [_case(name) for name in
            ("currently_authorized", "revoked", "erased", "cross_tenant")]
    false_blocks = sum(row["expected_accept"] and not row["governed_accepts"] for row in rows)
    stale_accepts = sum(row["case"] in {"revoked", "erased"}
                        and row["weak_stale_snapshot_accepts"] for row in rows)
    weak_unauthorized = sum(not row["expected_accept"]
                            and row["weak_stale_snapshot_accepts"] for row in rows)
    return {"schema": "cdm-governance-ablation-v1", "cases": rows,
        "metrics": {"valid_case_false_blocks": false_blocks,
            "governed_unauthorized_accepts": sum(not row["expected_accept"]
                                                  and row["governed_accepts"] for row in rows),
            "weak_stale_evidence_accepts": stale_accepts,
            "weak_unauthorized_accepts": weak_unauthorized,
            "governed_unauthorized_metadata_exposures": sum(
                row["governed_metadata_exposed"] for row in rows),
            "weak_unauthorized_metadata_exposures": sum(
                row["weak_metadata_exposed"] for row in rows)},
        "safety": {"network_calls": 0, "tool_calls": 0, "authority_changes": 0,
                   "plaintext_reported": False},
        "scope": "four deterministic in-memory fixtures; not a population rate or privacy certification"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="research/results/cdm/governance-ablation-r10")
    args = parser.parse_args()
    result = run()
    output = Path(args.out)
    output.mkdir(parents=True, exist_ok=True)
    path = output / "report.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    protocol = Path(__file__).resolve().parents[1] / "research" / "prereg" / \
        "cdm-r10-governance-ablation.md"
    manifest = {"schema": "cdm-governance-ablation-manifest-v1",
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "protocol": "research/prereg/cdm-r10-governance-ablation.md",
        "protocol_sha256": hashlib.sha256(protocol.read_bytes()).hexdigest(),
        "report_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "metrics": result["metrics"], "safety": result["safety"]}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                                           encoding="utf-8")
    print(json.dumps(manifest, sort_keys=True))
    return 0 if (manifest["metrics"]["valid_case_false_blocks"] == 0
                 and manifest["metrics"]["governed_unauthorized_accepts"] == 0
                 and manifest["metrics"]["weak_unauthorized_accepts"] == 3) else 1


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import json
from pathlib import Path
import runpy

import pytest


ROOT = Path(__file__).resolve().parents[1]
GATE = runpy.run_path(str(ROOT / "tools" / "agent_outcome_gate.py"))


def test_checked_in_manifest_is_immutable_versioned_and_requires_model_status() -> None:
    manifest, digest = GATE["load_manifest"](
        ROOT / "tools" / "agent_outcome_gate_manifest.v1.json"
    )

    assert manifest["immutable"] is True
    assert manifest["manifest_version"] == 1
    assert len(digest) == 64
    assert next(item for item in manifest["conditions"]
                if item["id"] == "real_agent_execution")["status"] == "NOT_RUN"


@pytest.mark.parametrize(
    ("statuses", "expected"),
    [
        (["PASS", "NOT_RUN"], "NOT_RUN"),
        (["PASS", "FAIL"], "FAIL"),
        (["PASS", "PASS"], "PASS"),
    ],
)
def test_overall_status_never_promotes_skipped_required_conditions(statuses, expected) -> None:
    results = [
        {"required": True, "status": status} for status in statuses
    ]

    assert GATE["overall_status"](results) == expected


def test_manifest_cannot_predeclare_model_execution_pass(tmp_path: Path) -> None:
    manifest = {
        "schema_id": "memory-fabric.agent-outcome-gate-manifest.v1",
        "manifest_version": 1,
        "immutable": True,
        "conditions": [{
            "id": "real_agent_execution", "required": True,
            "status": "PASS", "reason": "not run",
        }],
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="never predeclared PASS"):
        GATE["load_manifest"](path)

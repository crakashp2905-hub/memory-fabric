from __future__ import annotations

import json
from pathlib import Path
import runpy
import subprocess

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
    attack_gate = next(item for item in manifest["conditions"]
                       if item["id"] == "registered_adversarial_families")
    assert attack_gate["required"] is True
    assert attack_gate["command"] == ["python", "tools/adversarial_gate.py"]
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


def test_manifest_requires_registered_attack_family_gate(tmp_path: Path) -> None:
    source = json.loads((ROOT / "tools" / "agent_outcome_gate_manifest.v1.json")
                        .read_text(encoding="utf-8"))
    source["conditions"] = [item for item in source["conditions"]
                            if item["id"] != "registered_adversarial_families"]
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(source), encoding="utf-8")

    with pytest.raises(ValueError, match="registered_adversarial_families"):
        GATE["load_manifest"](path)


def test_source_identity_rejects_dirty_tree(tmp_path: Path) -> None:
    source_identity = GATE["source_identity"]
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email",
                    "test@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name",
                    "Test"], check=True)
    tracked = tmp_path / "source.txt"
    tracked.write_text("candidate\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "source.txt"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "candidate"], check=True)

    clean = source_identity(tmp_path)
    assert len(clean["commit_sha"]) == 40
    assert clean["clean"] is True

    tracked.write_text("modified\n", encoding="utf-8")
    dirty = source_identity(tmp_path)
    assert dirty["commit_sha"] == clean["commit_sha"]
    assert dirty["clean"] is False

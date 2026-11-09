from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import offline_qualification as oq  # noqa: E402


def test_scope_has_exactly_260_unique_tasks() -> None:
    rows = oq.parse_scope(oq.SCOPE.read_text(encoding="utf-8"))
    assert len(rows) == len({row["id"] for row in rows}) == 260
    assert "R2-10" in {row["id"] for row in rows}


def test_scope_parser_accepts_checked_and_unchecked_task_boxes() -> None:
    text = oq.SCOPE.read_text(encoding="utf-8")
    assert len(oq.parse_scope(text)) == 260
    unchecked = text.replace("- [x] **R2-10", "- [ ] **R2-10")
    assert len(oq.parse_scope(unchecked)) == 260


def test_generated_ledger_is_current() -> None:
    data = oq.build()
    committed = json.loads(oq.REGISTER.read_text(encoding="utf-8"))
    # The dirty flag changes while regenerating generated files; compare the
    # normalized content that the qualification decision actually uses.
    assert oq.normalized_digest(committed) == oq.normalized_digest(data)
    assert oq.REPORT.read_text(encoding="utf-8") == oq.render(committed)


def test_negative_control_missing_evidence_is_marked_incomplete(monkeypatch: pytest.MonkeyPatch) -> None:
    original = oq.load_overrides()
    corrupted = copy.deepcopy(original)
    corrupted["E1-01"]["evidence_paths"].append("missing/corrupted-result.json")
    monkeypatch.setattr(oq, "load_overrides", lambda: corrupted)
    row = next(row for row in oq.build()["tasks"] if row["task_id"] == "E1-01")
    assert row["status"] == "INCOMPLETE"
    assert row["acceptance_passed"] is False
    assert row["evidence_issues"]["missing/corrupted-result.json"] == "file is missing"


def test_malformed_json_evidence_is_marked_incomplete(monkeypatch: pytest.MonkeyPatch) -> None:
    scratch = ROOT / ".test-tmp"
    scratch.mkdir(exist_ok=True)
    bad = scratch / "malformed-evidence.json"
    bad.write_text("{broken", encoding="utf-8")
    original = oq.load_overrides()
    corrupted = copy.deepcopy(original)
    corrupted["E1-01"]["evidence_paths"].append(".test-tmp/malformed-evidence.json")
    monkeypatch.setattr(oq, "load_overrides", lambda: corrupted)
    row = next(row for row in oq.build()["tasks"] if row["task_id"] == "E1-01")
    assert row["status"] == "INCOMPLETE"
    assert "invalid .json evidence" in row["evidence_issues"][".test-tmp/malformed-evidence.json"]


def test_evidence_content_is_bound_by_sha256() -> None:
    row = next(row for row in oq.build()["tasks"] if row["task_id"] == "E1-07")
    for path, digest in row["evidence_digests"].items():
        assert len(digest) == 64
        assert digest == oq.sha256(ROOT / path)


def test_negative_control_corrupts_expected_result_then_restores_pass() -> None:
    scratch = ROOT / ".test-tmp"
    scratch.mkdir(exist_ok=True)
    artifact = scratch / "expected-result.json"
    relative = ".test-tmp/expected-result.json"
    original = b'{"decision":"PASS","solved":7}\n'
    artifact.write_bytes(original)
    expected = {"decision": "PASS", "solved": 7}
    assert oq.verify_expected_json(relative, expected) == []
    try:
        artifact.write_bytes(b'{"decision":"PASS","solved":6}\n')
        failures = oq.verify_expected_json(relative, expected)
        assert failures == ["solved: expected 7, observed 6"]
    finally:
        artifact.write_bytes(original)
    assert oq.verify_expected_json(relative, expected) == []


@pytest.mark.parametrize(
    "declared,observed,expected",
    [([1, 2, 3], [1, 2], "missing"), ([1, 2], [1, 2, 3], "extra"),
     ([1, 2], [1, 1, 2], "repeated")],
)
def test_seed_cherry_picking_is_rejected(declared, observed, expected) -> None:
    assert any(expected in issue for issue in oq.validate_seed_outputs(declared, observed))


@pytest.mark.parametrize(
    "output_seeds,expected_issue",
    [([1], "missing seeds"), ([1, 1, 2], "repeated seed output"), ([1, 2, 3], "extra seeds")],
)
def test_seed_manifest_checks_result_files_on_disk(tmp_path: Path, output_seeds, expected_issue) -> None:
    outputs = []
    for index, seed in enumerate(output_seeds):
        rel = f"result-{index}.json"
        (tmp_path / rel).write_text(json.dumps({"seed": seed, "score": 1}), encoding="utf-8")
        outputs.append({"seed": seed, "path": rel})
    manifest = {"schema": "memory-fabric-seed-manifest/1", "declared_seeds": [1, 2], "outputs": outputs}
    path = tmp_path / "seeds.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    issues = oq.verify_seed_manifest(path, root=tmp_path)
    assert any(expected_issue in issue for issue in issues)


def test_seed_manifest_accepts_exact_outputs_on_disk(tmp_path: Path) -> None:
    outputs = []
    for seed in (11, 12):
        rel = f"seed-{seed}.json"
        (tmp_path / rel).write_text(json.dumps({"seed": seed, "score": seed}), encoding="utf-8")
        outputs.append({"seed": seed, "path": rel})
    path = tmp_path / "seeds.json"
    path.write_text(json.dumps({"schema": "memory-fabric-seed-manifest/1",
                                "declared_seeds": [11, 12], "outputs": outputs}), encoding="utf-8")
    assert oq.verify_seed_manifest(path, root=tmp_path) == []


def test_full_attestation_is_refused_while_p0_is_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    scope = tmp_path / "scope.md"
    lines = oq.SCOPE.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        if line.startswith("- [x]") and "· **P0** ·" in line:
            lines[index] = line.replace("- [x]", "- [ ]", 1)
            break
    else:
        raise AssertionError("fixture scope has no completed P0 task")
    scope.write_text("\n".join(lines) + "\n", encoding="utf-8")
    overrides = tmp_path / "evidence.json"
    overrides.write_text(json.dumps({"tasks": []}), encoding="utf-8")
    monkeypatch.setattr(oq, "SCOPE", scope)
    monkeypatch.setattr(oq, "OVERRIDES", overrides)

    data = oq.build()
    assert data["summary"]["p0_open"] > 0
    assert data["summary"]["internal_status"] == "BLOCKED"
    assert all(status == "BLOCKED" for status in data["gates"].values())

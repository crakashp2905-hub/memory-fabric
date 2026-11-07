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


@pytest.mark.parametrize(
    "declared,observed,expected",
    [([1, 2, 3], [1, 2], "missing"), ([1, 2], [1, 2, 3], "extra"),
     ([1, 2], [1, 1, 2], "repeated")],
)
def test_seed_cherry_picking_is_rejected(declared, observed, expected) -> None:
    assert any(expected in issue for issue in oq.validate_seed_outputs(declared, observed))


def test_full_attestation_is_refused_while_p0_is_open() -> None:
    data = oq.build()
    assert data["summary"]["p0_open"] > 0
    assert data["summary"]["internal_status"] == "BLOCKED"
    assert all(status == "BLOCKED" for status in data["gates"].values())

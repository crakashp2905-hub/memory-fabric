from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from benchmarks.provenance import stamp, validate

ROOT = Path(__file__).resolve().parents[1]


def test_exact_head_is_stamped_and_validated() -> None:
    data = stamp({"result": 1}, root=ROOT)
    assert len(data["source"]["commit"]) == 40
    assert data["source"]["dirty"] is False
    assert validate(data, root=ROOT) == []


def test_unknown_or_abbreviated_sha_is_rejected() -> None:
    assert any("exact 40-character" in issue for issue in validate(
        {"source": {"commit": "abc1234", "dirty": False, "classification": "QUALIFIED"}}, root=ROOT))
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
                          capture_output=True, text=True).stdout.strip()
    assert any("unknown" in issue for issue in validate(
        {"source": {"commit": "0" * 40, "dirty": False, "classification": "QUALIFIED"}}, root=ROOT))
    assert len(head) == 40


def test_dirty_result_requires_explicit_exploratory_reason() -> None:
    data = {"source": {"commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
             check=True, capture_output=True, text=True).stdout.strip(), "dirty": True,
             "classification": "QUALIFIED"}}
    assert any("EXPLORATORY" in issue for issue in validate(data, root=ROOT))
    data["source"].update(classification="EXPLORATORY", reason="local iteration")
    assert validate(data, root=ROOT) == []


def test_stamp_refuses_dirty_checkout_without_exploratory_label() -> None:
    with pytest.raises(ValueError, match="dirty source"):
        stamp({}, root=ROOT)
    data = stamp({}, exploratory=True, reason="local iteration", root=ROOT)
    assert data["source"]["dirty"] is True
    assert validate(data, root=ROOT) == []

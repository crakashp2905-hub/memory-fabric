from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import offline_baseline as baseline  # noqa: E402


def test_baseline_is_byte_deterministic() -> None:
    first = json.dumps(baseline.build(), sort_keys=True, separators=(",", ":"))
    second = json.dumps(baseline.build(), sort_keys=True, separators=(",", ":"))
    assert first == second
    assert baseline.validate(json.loads(first)) == []


def test_manifest_rejects_missing_environment_field() -> None:
    data = copy.deepcopy(baseline.build())
    del data["environment"]["sqlite"]
    assert any("sqlite" in issue for issue in baseline.validate(data))


def test_manifest_rejects_tampered_input_digest() -> None:
    data = copy.deepcopy(baseline.build())
    key = next(iter(data["inputs"]))
    data["inputs"][key] = "0" * 64
    assert baseline.validate(data) == [f"input digest mismatch: {key}"]


def test_optional_absence_is_not_reported_as_pass() -> None:
    for row in baseline.build()["optional_capabilities"].values():
        assert row["status"] in {"AVAILABLE", "UNAVAILABLE"}
        if row["status"] == "UNAVAILABLE":
            assert row["reason"] and "NOT_TESTED" in row["impact"]

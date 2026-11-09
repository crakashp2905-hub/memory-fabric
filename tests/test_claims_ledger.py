from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import claims_ledger  # noqa: E402


def test_claims_ledger_is_valid_and_current() -> None:
    data = claims_ledger.build()
    assert {row["class"] for row in data["claims"]} >= {
        "deterministic-agent-simulation", "single-host-network", "retrieval-benchmark"
    }
    assert all(row["limitation"] and row["commit"] for row in data["claims"])
    assert json.loads(claims_ledger.OUT_JSON.read_text(encoding="utf-8")) == data
    assert claims_ledger.OUT_MD.read_text(encoding="utf-8") == claims_ledger.markdown(data)

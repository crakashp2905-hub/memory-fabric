from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import check as check_runner  # noqa: E402
import dependency_provenance as provenance  # noqa: E402


def test_check_runner_reports_unavailable_tools_without_green_claim(monkeypatch, capsys):
    monkeypatch.setattr(check_runner, "STEPS", [])
    real_find_spec = importlib.util.find_spec
    monkeypatch.setattr(check_runner.importlib.util, "find_spec",
                        lambda name: None if name == "bandit" else real_find_spec(name))
    assert check_runner.main([]) == 0
    output = capsys.readouterr().out
    assert "bandit: UNAVAILABLE" in output
    assert "ruff: AVAILABLE" in output
    assert "all checks passed" in output


def test_dependency_inventory_marks_lock_and_reproducibility_gaps(monkeypatch):
    target = ROOT / "research" / "results" / "h5-01-dependency-provenance.json"
    monkeypatch.setattr(provenance, "ROOT", ROOT)
    assert provenance.main() == 0
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["project"]["core_dependencies"] == []
    assert data["project"]["optional_dependencies"]
    assert data["lock_metadata"].startswith("UNAVAILABLE")
    assert data["reproducible_build"].startswith("NOT_ESTABLISHED")
    assert data["source"]["commit"]

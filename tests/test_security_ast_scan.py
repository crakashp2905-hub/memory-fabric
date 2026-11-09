from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import security_ast_scan as scanner  # noqa: E402


def test_known_positive_dangerous_fixture_fails() -> None:
    fixture = Path(__file__).parent / "data" / "security_ast_positive.py"
    findings = scanner.scan([fixture])
    assert [finding["category"] for finding in findings] == ["dynamic-code"]


def test_exception_requires_rationale_and_exact_match() -> None:
    fixture = Path(__file__).parent / "data" / "security_ast_positive.py"
    finding = scanner.findings_for(fixture.read_text(encoding="utf-8"),
                                   fixture.resolve().relative_to(scanner.ROOT).as_posix())[0]
    exception = {"file": finding["file"], "line": str(finding["line"]),
                 "category": str(finding["category"]), "rationale": "Test-only positive fixture."}
    assert scanner.scan([fixture], [exception]) == []
    exception["rationale"] = " "
    assert scanner.scan([fixture], [exception])[0]["category"] == "dynamic-code"

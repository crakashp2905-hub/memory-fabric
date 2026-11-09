from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import audit_package_assets as audit  # noqa: E402


def test_packaged_secret_fixture_is_rejected() -> None:
    findings = audit.audit_members(
        [("memory_fabric/unsafe.py", b"password = 'hunter2'\n")], "wheel")
    assert any(item["kind"] == "secret-finding" for item in findings)


def test_unexpected_binary_and_corpus_members_are_rejected() -> None:
    findings = audit.audit_members([
        ("memory_fabric/model.bin", b"\x00\xff"),
        ("tests/corpus/credentials.json", b"{}"),
    ], "wheel")
    assert {item["kind"] for item in findings} == {"unexpected-member"}


def test_declared_text_assets_and_package_metadata_are_accepted() -> None:
    findings = audit.audit_members([
        ("memory_fabric/core.py", b"value = 1\n"),
        ("memory_fabric/observability/static/dashboard.html", b"<html></html>"),
        ("memory_fabric-1.0.dist-info/METADATA", b"Name: memory-fabric\n"),
    ], "wheel")
    assert findings == []


@pytest.mark.parametrize("kind,name", [
    ("wheel", "memory_fabric/data.db"),
    ("sdist", "memory_fabric-1.0/tests/test_data.json"),
])
def test_unexpected_assets_are_rejected(kind: str, name: str) -> None:
    assert audit.audit_members([(name, b"data")], kind)

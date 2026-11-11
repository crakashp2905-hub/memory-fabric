"""Prove the pinned UTCP manual checker rejects a frozen attack corpus without I/O."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from memory_fabric.tool_protocol import ToolProtocolError, discover_utcp  # noqa: E402

CORPUS = ROOT / "tests" / "data" / "utcp_malicious_manuals.json"
SAFE_MANUAL = {
    "utcp_version": "1.0.1", "manual_version": "1.0.0", "tools": [{
        "name": "lookup", "description": "read a fixture", "consequential": False,
        "inputs": {"type": "object", "properties": {"id": {"type": "string"}},
                   "required": ["id"], "additionalProperties": False},
        "tool_call_template": {"call_template_type": "http",
                                "url": "https://api.example.com/lookup"},
    }],
}


def _forbidden_io(*_args: Any, **_kwargs: Any) -> None:
    raise AssertionError("manual policy validation attempted socket, file or URL I/O")


def evaluate() -> dict[str, Any]:
    # Read the frozen inputs before arming the guards. Discovery itself must
    # operate only over the already parsed in-memory data structures.
    cases = json.loads(CORPUS.read_text(encoding="utf-8"))
    rejected: list[dict[str, str]] = []
    accepted_safe: list[str] = []
    with (patch("socket.socket", side_effect=_forbidden_io),
          patch("pathlib.Path.open", side_effect=_forbidden_io),
          patch("builtins.open", side_effect=_forbidden_io),
          patch("urllib.request.urlopen", side_effect=_forbidden_io)):
        for case in cases:
            try:
                discover_utcp(case["manual"])
            except ToolProtocolError as exc:
                rejected.append({"case_id": case["id"], "reason": str(exc)})
            else:
                raise AssertionError(f"dangerous manual accepted: {case['id']}")
        descriptors = discover_utcp(SAFE_MANUAL)
        accepted_safe = [descriptor.name for descriptor in descriptors]
    passed = len(rejected) == len(cases) and accepted_safe == ["lookup"]
    return {
        "schema": "memory-fabric-n6-06-utcp-policy-check/1",
        "task_id": "N6-06", "acceptance_passed": passed,
        "evidence_level": "CONTRACT",
        "corpus": {"path": CORPUS.relative_to(ROOT).as_posix(),
                   "sha256": hashlib.sha256(CORPUS.read_bytes()).hexdigest(),
                   "cases": len(cases)},
        "rejected": rejected, "rejected_count": len(rejected),
        "accepted_safe_manual_tools": accepted_safe,
        "io_guards": {"socket": True, "path_open": True,
                      "builtin_open": True, "urlopen": True,
                      "triggered": False},
        "source": {"commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                               check=True, capture_output=True,
                                               text=True).stdout.strip(),
                   "dirty_before_result_write": bool(subprocess.run(
                       ["git", "status", "--porcelain"], cwd=ROOT, check=True,
                       capture_output=True, text=True).stdout.strip()),
                   "experiment_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
        "limitations": [
            "The corpus tests the repository's pinned UTCP subset and local parser; no live remote manual or network client is involved.",
            "The HTTP transport validator restricts destinations to public HTTPS origins, but the parser does not perform DNS resolution or authenticate endpoint behavior.",
        ],
    }


if __name__ == "__main__":
    report = evaluate()
    (ROOT / "research" / "results" / "n6-06-utcp-policy-check.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"task_id": report["task_id"], "corpus_cases": report["corpus"]["cases"],
                      "rejected": report["rejected_count"],
                      "safe_control": report["accepted_safe_manual_tools"],
                      "acceptance_passed": report["acceptance_passed"]}, indent=2))

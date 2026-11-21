#!/usr/bin/env python3
"""Fail documentation qualification on numeric outcome claims without evidence (W01-09).

    python tools/claim_scanner.py            # list unsupported claims; exit 1 if any
    python tools/claim_scanner.py --json     # machine-readable report

Scans the current-state documents (README, the agent-outcome and CDM decision
documents, the release checklist, and new agent-outcome result summaries). A
*numeric outcome claim* is a paragraph that contains an outcome word (success,
completion, withholding, recall, gain, utility, ...) together with a rate, a
percentage, a fraction such as ``12/12`` or a signed difference such as ``+0.20``.
Version strings and hexadecimal digests are not numbers for this purpose.

A claim is supported when the same paragraph names evidence that exists in the
tree: a recorded result or preregistration under ``research/``, a benchmark under
``benchmarks/``, or the test that fixes a contract fixture (``tests/test_x.py`` or
``tests.test_x``). Otherwise it must be listed in ``tools/claim_scanner_allowlist.json``
with the exact text it covers, a reason and a date. Historical documents
(release notes, the changelog) are deliberately not scanned: they are never rewritten.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ALLOWLIST = ROOT / "tools" / "claim_scanner_allowlist.json"
TARGETS = (
    "README.md",
    "docs/AGENT_OUTCOME_EVALUATION.md",
    "docs/OUTCOME_PROTOCOL_EVALUATION.md",
    "docs/CDM_INTERNAL_GO_NO_GO.md",
    "docs/CDM_KNOWN_FINDINGS.md",
    "docs/MEMORY_FABRIC_RELEASE_CHECKLIST.md",
)
TARGET_GLOBS = ("research/results/agent-outcomes/**/*.md",)

_VERSION = re.compile(r"\b\d+\.\d+\.\d+\b")
_HEX = re.compile(r"\b[0-9a-f]{7,64}\b")
_NUMBER = re.compile(
    r"(?<![\w.])(?:\d{1,3}(?:\.\d+)?\s?%|\d+\s?/\s?\d+|[+−-]\d*\.\d+|0\.\d{2,}"
    r"|\d+(?:\.\d+)?\s+percentage points)(?![\w/])")
_OUTCOME = re.compile(r"success|complet|withh|accura|recall|precision|improv|\bgain|\brate\b"
                      r"|abstain|abstention|utility|\bbeat|reduc|ndcg|recover", re.I)
_LINK = re.compile(r"\]\((?!https?:)([^)#\s]+)")
_PATH = re.compile(r"`((?:research|benchmarks|tests)/[^`\s]+)`")
_TEST_MODULE = re.compile(r"`?(tests\.test_[A-Za-z0-9_]+)`?")
EVIDENCE_ROOTS = ("research/", "benchmarks/", "tests/")


def _numbers(paragraph: str) -> list[str]:
    cleaned = _HEX.sub(" ", _VERSION.sub(" ", paragraph))
    return [match.group(0).strip() for match in _NUMBER.finditer(cleaned)]


def _evidence(paragraph: str, document: Path, root: Path) -> list[str]:
    found: list[str] = []
    for match in _LINK.finditer(paragraph):
        target = (document.parent / match.group(1)).resolve()
        try:
            rel = target.relative_to(root.resolve()).as_posix()
        except ValueError:
            continue
        if rel.startswith(EVIDENCE_ROOTS) and target.exists():
            found.append(rel)
    for match in _PATH.finditer(paragraph):
        if (root / match.group(1)).exists():
            found.append(match.group(1))
    for match in _TEST_MODULE.finditer(paragraph):
        rel = match.group(1).replace(".", "/") + ".py"
        if (root / rel).exists():
            found.append(rel)
    return sorted(set(found))


def load_allowlist(path: Path = ALLOWLIST) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    entries = json.loads(path.read_text(encoding="utf-8")).get("entries", [])
    for entry in entries:
        if set(entry) != {"file", "contains", "reason", "date"}:
            raise ValueError(f"allowlist entry fields must be file/contains/reason/date: {entry}")
        if not entry["reason"].strip() or not entry["contains"].strip():
            raise ValueError("allowlist entries need the covered text and a reason")
        date.fromisoformat(entry["date"])
    return entries


def targets(root: Path = ROOT) -> list[Path]:
    paths = [root / rel for rel in TARGETS if (root / rel).is_file()]
    for pattern in TARGET_GLOBS:
        paths.extend(sorted(root.glob(pattern)))
    return paths


def scan(root: Path = ROOT, allowlist: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    allowlist = load_allowlist() if allowlist is None else allowlist
    claims: list[dict[str, Any]] = []
    for document in targets(root):
        rel = document.relative_to(root).as_posix()
        in_fence = False
        for paragraph in re.split(r"\n\s*\n", document.read_text(encoding="utf-8")):
            if paragraph.count("```") % 2 == 1:
                in_fence = not in_fence
                continue
            if in_fence or paragraph.lstrip().startswith("```"):
                continue
            numbers = _numbers(paragraph)
            if not numbers or not _OUTCOME.search(paragraph):
                continue
            evidence = _evidence(paragraph, document, root)
            allowed = [entry for entry in allowlist
                       if entry["file"] == rel and entry["contains"] in paragraph]
            claims.append({"file": rel, "numbers": numbers[:8], "evidence": evidence,
                           "allowlisted": bool(allowed),
                           "supported": bool(evidence) or bool(allowed),
                           "excerpt": " ".join(paragraph.split())[:160]})
    unsupported = [claim for claim in claims if not claim["supported"]]
    return {"schema_id": "memory-fabric.claim-scan.v1", "claims": claims,
            "unsupported": unsupported, "status": "FAIL" if unsupported else "PASS"}


def main(argv: list[str]) -> int:
    report = scan()
    if "--json" in argv:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        for claim in report["unsupported"]:
            print(f"UNSUPPORTED {claim['file']}: {', '.join(claim['numbers'])} :: {claim['excerpt']}")
        print(f"{report['status']}: {len(report['claims'])} numeric outcome claims, "
              f"{len(report['unsupported'])} without evidence")
    return 1 if report["unsupported"] else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

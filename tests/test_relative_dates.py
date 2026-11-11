"""Narrative docs must not say "today" or "last week": they go stale the day after.

Quoted or backticked text is exempt, because it is data (a fixture sentence, an
example question, a command). Write the date instead: "as of 2026-10-24", or
"at this commit", or the version.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP = {".git", "build", "dist", "node_modules", "__pycache__", ".tmp", ".tmp-cdm"}
RELATIVE = re.compile(
    r"\b(today|yesterday|tomorrow|last (week|month|year|quarter)|this (week|month|quarter)|just now)\b",
    re.IGNORECASE)


def narrative_lines(path: Path):
    for number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        yield number, re.sub(r'"[^"]*"', "", re.sub(r"`[^`]*`", "", line))


class TestRelativeDates(unittest.TestCase):
    def test_markdown_prose_names_dates_not_relative_days(self) -> None:
        offenders = []
        # A quotation that breaks across lines is not seen by the per-line check:
        # this one is an example question, not narration.
        exempt_text = {"what did we believe it was last year?"}
        for path in ROOT.rglob("*.md"):
            relative = path.relative_to(ROOT)
            if SKIP.intersection(relative.parts):
                continue
            for number, text in narrative_lines(path):
                if RELATIVE.search(text) and not any(t in text for t in exempt_text):
                    offenders.append(f"{relative.as_posix()}:{number}: {text.strip()[:100]}")
        self.assertEqual(offenders, [], "use an absolute date, a version or 'at this commit'")


if __name__ == "__main__":
    unittest.main()

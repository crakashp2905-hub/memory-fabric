"""Every relative link in the repository's Markdown points at a file that exists."""

from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")


def tracked_markdown() -> list[Path]:
    out = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard", "*.md"], capture_output=True, text=True, cwd=ROOT)
    # docs/ci-evidence holds frozen snapshots of docs from an earlier commit; their
    # relative links point at that commit's root, so they are evidence, not live docs.
    return [ROOT / p for p in out.stdout.split() if p and not p.startswith("docs/ci-evidence/")]


def broken() -> list[str]:
    bad = []
    for doc in tracked_markdown():
        text = re.sub(r"```.*?```", "", doc.read_text(encoding="utf-8"), flags=re.S)
        for target in LINK.findall(text):
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            path = unquote(target.split("#", 1)[0])
            if not path:
                continue
            if not (doc.parent / path).exists():
                bad.append(f"{doc.relative_to(ROOT).as_posix()} -> {target}")
    return bad


class DocLinks(unittest.TestCase):
    def test_no_broken_relative_links(self) -> None:
        self.assertEqual(broken(), [])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

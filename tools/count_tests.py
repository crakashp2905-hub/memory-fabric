"""Count the complete pytest collection used by CI, and keep documents in step.

    python tools/count_tests.py           # print the count
    python tools/count_tests.py --write   # also rewrite the cited numbers

CI runs the full pytest collection. This includes unittest TestCase classes
and pytest-style functions, so the count reflects every executed test.

The documents that state a current count cite this number:
`docs/VALIDATION.md`'s current-baseline row and the README, which defers to
it. Dated records (an audit at a past commit, a release evaluation) keep the
number they had at their date and are not rewritten. The hygiene test fails
when a current number drifts, and `--write` is the fix it names.
"""

from __future__ import annotations

import argparse
import re
import sys
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# (document, pattern whose group 1 is the count)
CURRENT = (
    ("docs/VALIDATION.md", re.compile(r"(?m)^\| Unit, integration, property \| [^|]+\| \*\*(\d+) tests\*\*")),
    ("README.md", re.compile(r"\*\*(\d+) tests\*\* \(see \[the current baseline\]")),
)


def count() -> int:
    done = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-qq", "tests"],
                          cwd=ROOT, capture_output=True, text=True)
    if done.returncode:
        raise RuntimeError(f"pytest collection failed:\n{done.stdout}\n{done.stderr}")
    counts = [int(value) for value in re.findall(r"(?m)^.+\.py:\s+(\d+)\s*$", done.stdout)]
    if not counts:
        raise RuntimeError("pytest collection produced no per-file counts")
    return sum(counts)


def cited() -> dict[str, int | None]:
    found: dict[str, int | None] = {}
    for doc, pattern in CURRENT:
        match = pattern.search((ROOT / doc).read_text(encoding="utf-8"))
        found[doc] = int(match.group(1)) if match else None
    return found


def write(n: int) -> list[str]:
    changed = []
    for doc, pattern in CURRENT:
        path = ROOT / doc
        text = path.read_text(encoding="utf-8")
        match = pattern.search(text)
        if match is None:
            raise SystemExit(f"{doc}: the count pattern no longer matches")
        if int(match.group(1)) != n:
            start, end = match.span(1)
            path.write_text(text[:start] + str(n) + text[end:], encoding="utf-8")
            changed.append(doc)
    return changed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true", help="fail if cited counts differ from source")
    args = parser.parse_args(argv)
    n = count()
    print(n)
    if args.write:
        for doc in write(n):
            print(f"updated {doc}", file=sys.stderr)
    if args.check:
        stale = {doc: value for doc, value in cited().items() if value != n}
        for doc, value in stale.items():
            print(f"{doc}: cites {value}, source suite has {n}; run tools/count_tests.py --write",
                  file=sys.stderr)
        return 1 if stale else 0
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

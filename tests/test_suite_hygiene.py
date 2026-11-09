"""Guard the exact test collection and runner used by CI."""

from __future__ import annotations

import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class TestCIRunner(unittest.TestCase):
    def test_ci_installs_pinned_pytest_and_collects_entire_tests_tree(self) -> None:
        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertIn("pytest==9.0.3", project["project"]["optional-dependencies"]["test"])
        workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        self.assertIn('python -m pip install -e ".[test]"', workflow)
        self.assertIn("python -m pytest tests -q", workflow)


class TestCitedCountsAreCurrent(unittest.TestCase):
    def test_documents_cite_the_real_count(self) -> None:
        import sys
        sys.path.insert(0, str(ROOT / "tools"))
        import count_tests

        n = count_tests.count()
        for doc, cited in count_tests.cited().items():
            with self.subTest(doc=doc):
                self.assertIsNotNone(cited, f"{doc}: no current test count found")
                self.assertEqual(cited, n, f"{doc} cites {cited} tests; collection has {n}. "
                                 "Fix: python tools/count_tests.py --write")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

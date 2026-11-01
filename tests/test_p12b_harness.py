"""The HTTP load harness runs from a clean source checkout."""

from __future__ import annotations

import os
import unittest

from experiments.p12b_api_load import ROOT, subprocess_env


class SourceCheckoutEnvironment(unittest.TestCase):
    def test_subprocess_can_import_the_src_layout(self) -> None:
        paths = subprocess_env()["PYTHONPATH"].split(os.pathsep)
        self.assertEqual(paths[0], str(ROOT / "src"))


if __name__ == "__main__":
    unittest.main()

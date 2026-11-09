"""The release gate must be runnable in restricted Windows temp layouts."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tools.adversarial_gate import configure_temp


class ExplicitTempRoot(unittest.TestCase):
    def test_configures_stdlib_and_child_process_temp_roots(self) -> None:
        previous = tempfile.tempdir
        previous_temp = os.environ.get("TEMP")
        previous_tmp = os.environ.get("TMP")
        try:
            with TemporaryDirectory(dir=Path.cwd()) as parent:
                selected = Path(parent) / "gate-temp"
                self.assertEqual(configure_temp(selected), str(selected.resolve()))
                self.assertEqual(Path(tempfile.gettempdir()), selected.resolve())
                self.assertEqual(os.environ["TEMP"], str(selected.resolve()))
                self.assertEqual(os.environ["TMP"], str(selected.resolve()))
        finally:
            tempfile.tempdir = previous
            if previous_temp is None:
                os.environ.pop("TEMP", None)
            else:
                os.environ["TEMP"] = previous_temp
            if previous_tmp is None:
                os.environ.pop("TMP", None)
            else:
                os.environ["TMP"] = previous_tmp


if __name__ == "__main__":
    unittest.main()

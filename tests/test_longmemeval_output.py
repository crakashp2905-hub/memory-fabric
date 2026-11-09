"""LongMemEval evidence output is machine-readable and self-consistent."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from experiments.longmemeval_bench import write_result


class EvidenceWriter(unittest.TestCase):
    def test_json_output_also_gets_a_markdown_companion(self) -> None:
        result = {
            "split": "s", "instances": 0, "abstention": 0, "k": 10,
            "temporal": "as_of", "median_turns": 0, "max_turns": 0,
            "arms": {}, "by_type": {}, "type_counts": {},
        }
        with TemporaryDirectory(dir=Path.cwd()) as folder:
            json_path, md_path = write_result(Path(folder) / "run.json", result)
            self.assertEqual(json.loads(json_path.read_text(encoding="utf-8")), result)
            self.assertTrue(md_path.read_text(encoding="utf-8").startswith("# LongMemEval"))


if __name__ == "__main__":
    unittest.main()

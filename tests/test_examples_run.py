"""Every offline example runs to completion from a clean process."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OFFLINE = ["getting_started", "quickstart", "wrong_memory_demo", "reference_agent",
           "poisoning_and_rollback", "action_gate", "multi_agent_team", "sdk_workflow",
           "agent_on_the_fabric", "why_blocked", "memory_vs_json",
           "correction_spares_unrelated_action", "multi_agent_provenance_dispute",
           "correction_strategy_comparison", "outcome_recovery_demo", "outcome_recovery_demo_typed"]


class Examples(unittest.TestCase):
    def test_offline_examples_run(self) -> None:
        listed = {p.stem for p in (ROOT / "examples").glob("*.py")}
        self.assertEqual(listed - set(OFFLINE), {"live_memory_os", "live_memory_os_typed"},
                         "a new example must be added here, or to the live list")
        for source in (ROOT / "examples").glob("*.py"):
            self.assertIn("DEMO ONLY:", source.read_text(encoding="utf-8"),
                          f"{source.name} must label simulation/model scope visibly")
        for name in OFFLINE:
            with self.subTest(example=name):
                done = subprocess.run([sys.executable, str(ROOT / "examples" / f"{name}.py")],
                                      capture_output=True, text=True, timeout=300, cwd=ROOT)
                self.assertEqual(done.returncode, 0, done.stderr[-2000:])
                self.assertIn("DEMO ONLY:", done.stdout)
                if name == "why_blocked":
                    example_source = (ROOT / "examples" / "why_blocked.py").read_text(
                        encoding="utf-8")
                    self.assertNotIn("fabric.log", example_source)
                    self.assertIn("evidence_withdrawn", done.stdout)
                    self.assertIn("Evidence pointer: memory", done.stdout)
                    self.assertIn("Repair: re-certify with current evidence", done.stdout)
                if name == "correction_strategy_comparison":
                    self.assertIn("naive delete", done.stdout)
                    self.assertIn("blanket", done.stdout)
                    self.assertIn("selective gate", done.stdout)
                    self.assertIn("false blocks", done.stdout)
                    self.assertIn("unrelated 34-psi action", done.stdout)
                if name == "multi_agent_provenance_dispute":
                    self.assertIn("share 1 source root", done.stdout)
                    self.assertIn("support is contested: True", done.stdout)
                    self.assertIn("14-bar support to 2 roots", done.stdout)
                    self.assertIn("not truth verification", done.stdout)
                if name == "memory_vs_json":
                    self.assertIn("Identical source records per arm: 2; equal input: True", done.stdout)
                    self.assertIn("JSON-style store: WOULD RUN", done.stdout)
                    self.assertIn("Memory Fabric:   BLOCKED (evidence_withdrawn)", done.stdout)
                    self.assertIn("Scope: a fixed scripted example", done.stdout)
                    self.assertIn("Ordinary baseline: SQLite key/value table with JSON record payloads.",
                                  done.stdout)

    def test_getting_started_runs_from_a_clean_offline_install(self) -> None:
        scratch = ROOT / ".test-tmp"
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temp:
            started = time.perf_counter()
            target = Path(temp) / "site-packages"
            install = subprocess.run(
                [sys.executable, "-m", "pip", "install", "--no-index", "--no-deps",
                 "--no-build-isolation", "--disable-pip-version-check", "--target",
                 str(target), str(ROOT)],
                capture_output=True, text=True, timeout=60, cwd=ROOT,
            )
            self.assertEqual(install.returncode, 0, install.stderr[-2000:])

            env = os.environ.copy()
            env["PYTHONPATH"] = str(target)
            database = Path(temp) / "getting-started.db"
            run = subprocess.run(
                [sys.executable, str(ROOT / "examples" / "getting_started.py"), str(database)],
                capture_output=True, text=True, timeout=60, cwd=temp, env=env,
            )
            self.assertEqual(run.returncode, 0, run.stderr[-2000:])
            self.assertIn("before correction: ALLOWED", run.stdout)
            self.assertIn("after correction:  BLOCKED", run.stdout)
            self.assertIn("revised fact visible: True", run.stdout)
            self.assertLess(time.perf_counter() - started, 60)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

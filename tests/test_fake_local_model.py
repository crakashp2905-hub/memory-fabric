"""The FAKE loopback model server (W20-08): real HTTP plumbing, never counted as inference."""

from __future__ import annotations

import importlib.util
import unittest

from benchmarks.fake_local_model import FAKE_MODEL, FakeLocalModelServer, is_fake
from benchmarks.outcome_arms import ARMS, build_task, run_arm
from benchmarks.outcome_model_team import ROOT, run_model_team


def preflight(host: str, model: str) -> dict:
    spec = importlib.util.spec_from_file_location("_pf", ROOT / "tools" / "model_preflight.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.preflight(host, [model])


class FakeServer(unittest.TestCase):
    def test_preflight_sees_the_fake_and_it_says_so(self) -> None:
        with FakeLocalModelServer() as host:
            report = preflight(host, FAKE_MODEL)
        self.assertEqual(report["status"], "MODELS_AVAILABLE")
        self.assertTrue(is_fake(report["runtime_version"], report["models"][0]["digest"]))

    def test_model_team_over_http_runs_but_is_never_model_evidence(self) -> None:
        with FakeLocalModelServer() as host:
            report = run_model_team(FAKE_MODEL, host=host, families=("public_correction",))
        self.assertEqual(report["status"], "FAKE_BACKEND")
        self.assertEqual(report["local_model_evidence"], "FAKE_BACKEND_NOT_EVIDENCE")
        self.assertEqual(report["evidence_type"], "fake_backend")
        scripted = {arm: run_arm(ARMS[arm], build_task("public_correction", 0))["terminal_status"]
                    for arm in ("A3", "A4", "A5")}
        for row in report["rows"]:
            self.assertGreater(row["inference_backed_steps"], 0)
            self.assertEqual(row["terminal_status"], scripted[row["arm"]], row["arm"])

    def test_real_looking_reports_are_not_fake(self) -> None:
        self.assertFalse(is_fake("0.5.1", "sha256:" + "a" * 64))
        self.assertTrue(is_fake("fake-1", None))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

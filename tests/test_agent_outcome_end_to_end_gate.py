"""The one offline end-to-end gate (W23-01, W23-02): report shape, evidence boundaries, fail-closed model stage."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("_e2e_gate", ROOT / "tools" / "agent_outcome_end_to_end_gate.py")
assert _spec is not None and _spec.loader is not None
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)

SHA = "a" * 40
PASS = {"status": "PASS"}


def rows(matrix: dict) -> dict[str, dict]:
    return {row["gate_id"]: row for row in matrix["rows"]}


class Matrix(unittest.TestCase):
    def test_passing_scripted_stages_make_only_the_synthetic_gate_scripted_pass(self) -> None:
        stages = {name: PASS for name in ("source", "contracts", "demo", "arms", "provenance")}
        matrix = rows(gate.build_matrix(stages, SHA))
        self.assertEqual(matrix["synthetic_outcome_gate"]["status"], "SCRIPTED_PASS")
        for other in ("main_ci", "model_attacks", "real_agent", "confirmatory", "independent_review"):
            self.assertEqual(matrix[other]["status"], "NOT_RUN", other)

    def test_a_failed_stage_fails_the_synthetic_gate(self) -> None:
        stages = {name: PASS for name in ("source", "contracts", "demo", "arms")}
        stages["provenance"] = {"status": "FAIL"}
        self.assertEqual(rows(gate.build_matrix(stages, SHA))["synthetic_outcome_gate"]["status"],
                         "FAILED")

    def test_a_missing_model_never_turns_into_model_evidence(self) -> None:
        stages = {name: PASS for name in ("source", "contracts", "demo", "arms", "provenance")}
        stages["local_model"] = {"status": "REAL_AGENT_NOT_RUN", "reason": "NO_LOCAL_MODEL_INSTALLED"}
        self.assertEqual(rows(gate.build_matrix(stages, SHA))["real_agent"]["status"], "NOT_RUN")

    def test_model_evidence_needs_this_commit_and_a_digest(self) -> None:
        stages = {name: PASS for name in ("source", "contracts", "demo", "arms", "provenance")}
        stages["local_model"] = {"status": "LOCAL_MODEL_EVIDENCE_AVAILABLE", "reason": "ran",
                                 "model": {"digest": "sha256:abc"}}
        row = rows(gate.build_matrix(stages, SHA))["real_agent"]
        self.assertEqual((row["status"], row["target_sha"]), ("LOCAL_MODEL_PASS", SHA))
        stages["local_model"]["model"] = {}
        with self.assertRaises(Exception):
            gate.build_matrix(stages, SHA)


class LocalModelStage(unittest.TestCase):
    def test_no_runtime_is_real_agent_not_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            with mock.patch.object(gate, "_run", side_effect=self._preflight({"status": "REAL_AGENT_NOT_RUN",
                                                                               "reason": "LOCAL_RUNTIME_UNAVAILABLE"})):
                stage = gate.stage_local_model("qwen2.5:1.5b", out, SHA)
        self.assertEqual(stage["status"], "REAL_AGENT_NOT_RUN")
        self.assertFalse(stage["required"])
        self.assertFalse(stage["scripted_substitute_used"])

    def test_a_model_team_report_from_another_commit_is_not_evidence(self) -> None:
        team = {"local_model_evidence": "LOCAL_MODEL_EVIDENCE_AVAILABLE",
                "candidate_commit_sha": "b" * 40, "model": {"digest": "sha256:abc"}}
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            with mock.patch.object(gate, "_run", side_effect=self._preflight(
                    {"status": "MODELS_AVAILABLE"}, team)):
                stage = gate.stage_local_model("qwen2.5:1.5b", out, SHA)
        self.assertEqual(stage["status"], "REAL_AGENT_NOT_RUN")

    @staticmethod
    def _preflight(report: dict, team: dict | None = None):
        def run(argv: list[str], log: Path, timeout: int = 0) -> tuple[int, float]:
            log.write_text("", encoding="utf-8")
            if "--out" in argv:
                target = Path(argv[argv.index("--out") + 1])
                payload = report if "model_preflight.py" in " ".join(argv) else team
                if payload is not None:
                    target.write_text(json.dumps(payload), encoding="utf-8")
            return 0, 0.0
        return run


class Report(unittest.TestCase):
    def test_partial_runs_are_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(SystemExit):
            gate.main(["--offline", "--out", directory])

    def test_report_is_written_even_when_a_stage_raises(self) -> None:
        def boom(*args, **kwargs):
            raise RuntimeError("stage exploded")
        with tempfile.TemporaryDirectory() as directory, \
                mock.patch.object(gate, "stage_demo", boom), \
                mock.patch.object(gate, "stage_commands", lambda name, commands, out: dict(PASS)), \
                mock.patch.object(gate, "stage_arms", lambda out: dict(PASS)), \
                mock.patch.object(gate, "stage_source", lambda out: {"status": "PASS", "commit_sha": SHA}):
            code = gate.main(["--offline", "--all", "--out", directory])
            report = json.loads((Path(directory) / "report.json").read_text())
            self.assertTrue((Path(directory) / "REPORT.md").is_file())
        self.assertEqual(code, 1)
        self.assertEqual(report["failed_stages"], ["demo"])
        self.assertIn("stage exploded", report["stages"]["demo"]["reason"])
        self.assertFalse(report["production_qualified"])
        self.assertEqual(rows(report["release_matrix"])["synthetic_outcome_gate"]["status"], "FAILED")

    def test_markdown_carries_every_stage_and_the_disclaimer(self) -> None:
        stages = {"source": PASS, "demo": {"status": "FAIL", "seconds": 1.0}}
        report = {"candidate_commit_sha": SHA, "status": "FAIL", "stages": stages,
                  "release_matrix": gate.build_matrix(stages, SHA)}
        text = gate.render_markdown(report)
        self.assertIn("| demo | FAIL | 1.0 |", text)
        self.assertIn("No row is a production qualification", text)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

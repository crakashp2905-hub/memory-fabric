"""The offline qualification gate keeps missing evidence explicit."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from tools.agent_outcome_gate import (
    MANIFEST_PATH, _run_check, overall_status, read_manifest,
    real_agent_team_evidence_result, real_agent_team_report_is_complete,
)


class TestAgentOutcomeGate(unittest.TestCase):
    def test_manifest_is_versioned_and_content_addressed(self) -> None:
        manifest, digest = read_manifest(MANIFEST_PATH)
        self.assertEqual(manifest["manifest_version"], 40)
        self.assertEqual(manifest["schema_id"], "memory-fabric.agent-outcome-gate.v40")
        self.assertEqual(len(digest), 64)
        self.assertIn("full_repository", [item["id"] for item in manifest["checks"]])
        self.assertIn("real_agent_team", [item["id"] for item in manifest["checks"]])

    def test_local_model_gate_requires_separate_completed_inference(self) -> None:
        manifest, _ = read_manifest(MANIFEST_PATH)
        check = next(item for item in manifest["checks"] if item["id"] == "local_model")
        result = _run_check(check, timeout_s=1, run_full=False)
        self.assertEqual(result["status"], "REAL_AGENT_NOT_RUN")

    def test_real_agent_team_manifest_is_validated_and_content_addressed(self) -> None:
        report_path = (Path(__file__).resolve().parents[1]
                       / "benchmarks" / "real_agent_team_smoke_manifest.json")
        result = real_agent_team_evidence_result(report_path)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["actor_ids"], ["observer", "planner", "executor"])
        self.assertEqual(result["model_calls"], 5)
        self.assertEqual(len(result["report_sha256"]), 64)

    def test_real_agent_team_gate_rejects_executor_parameter_drift(self) -> None:
        report_path = (Path(__file__).resolve().parents[1]
                       / "benchmarks" / "real_agent_team_smoke_manifest.json")
        report = json.loads(report_path.read_text(encoding="utf-8"))
        report["model_steps"][4]["arguments"]["parameters"]["value"] = 99
        self.assertFalse(real_agent_team_report_is_complete(report))

    def test_not_run_never_aggregates_to_qualification(self) -> None:
        checks = [
            {"required_for_scripted_qualification": True, "status": "PASS"},
            {"required_for_scripted_qualification": True, "status": "NOT_RUN"},
        ]
        self.assertEqual(overall_status(checks), "NOT_RUN")

    def test_required_failure_dominates_unrun_checks(self) -> None:
        checks = [
            {"required_for_scripted_qualification": True, "status": "NOT_RUN"},
            {"required_for_scripted_qualification": True, "status": "FAIL"},
        ]
        self.assertEqual(overall_status(checks), "FAIL")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

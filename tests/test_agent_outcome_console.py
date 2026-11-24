"""Read-only agent-outcome operator views (W21-01 .. W21-10)."""

from __future__ import annotations

import json
import os
import re
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http import HTTPStatus
from pathlib import Path
from unittest import mock

from memory_fabric import MemoryFabric
from memory_fabric.observability import outcomes
from memory_fabric.observability.server import build_server

ROOT = Path(__file__).resolve().parents[1]


def write_artifacts(directory: Path, *, arms=None) -> None:
    from benchmarks import outcome_performance as perf
    from benchmarks import outcome_poisoning
    from benchmarks.outcome_arms import run
    from benchmarks.outcome_episode import run_governed_episode
    from benchmarks.outcome_scorecard import scorecard
    from benchmarks.outcome_tenant_probe import run as probe

    arms = arms or run(seeds=1)
    files = {
        "scripted-arms-dev.json": arms,
        "scripted-scorecard-dev.json": scorecard(arms, source_sha="f" * 40, evidence_type="scripted"),
        "LAUNCH_DECISION.json": {"engineering": {"decision": "GO"}, "deployment": {"decision": "HOLD"}},
        "performance-dev.json": {"cdm_cost": perf.cdm_cost(seeds=1), "host": perf.host()},
        "poisoning-dev.json": outcome_poisoning.run(),
        "tenant-probe-dev.json": probe(trials=5),
        "demo-episode-trace.json": run_governed_episode(1)["record"]["trace"],
    }
    for name, payload in files.items():
        (directory / name).write_text(json.dumps(payload), encoding="utf-8")


class ViewModel(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory()
        write_artifacts(Path(cls.tmp.name))
        cls.view = outcomes.build_view(cls.tmp.name)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def test_unconfigured_is_said_plainly(self) -> None:
        view = outcomes.build_view(None)
        self.assertEqual((view["status"], view["controls"]), ("NOT_CONFIGURED", []))

    def test_task_summary_has_completion_failures_withholding_unsafe_and_resources(self) -> None:
        a5 = self.view["summary"]["by_arm"]["A5"]
        for key in ("completion", "false_withholding", "unsafe_attempts_refused_by_gate",
                    "unsafe_executed", "steps", "tool_calls"):
            self.assertIn(key, a5)
        self.assertEqual(a5["model_tokens"], "NOT_MEASURED")

    def test_timeline_steps_cite_audit_records_and_carry_no_content(self) -> None:
        steps = self.view["timeline"]["steps"]
        kinds = [s["kind"] for s in steps]
        for kind in ("world_events", "retrieved", "proposed", "verified", "effect"):
            self.assertIn(kind, kinds)
        self.assertTrue(all(s["audit_ref"] for s in steps))
        self.assertNotIn("reading is", json.dumps(self.view["timeline"]))

    def test_comparison_marks_missing_arms_not_run_and_never_zero(self) -> None:
        arms = self.view["comparison"]["arms"]
        self.assertEqual({a: arms[a]["status"] for a in ("A3", "A4", "A5", "A6")},
                         {"A3": "RUN", "A4": "RUN", "A5": "RUN", "A6": "RUN"})
        trimmed = json.loads((Path(self.tmp.name) / "scripted-scorecard-dev.json").read_text())
        trimmed["arms"].pop("A6")
        self.assertEqual(outcomes.comparison_view(trimmed, None)["arms"]["A6"], {"status": "NOT_RUN"})
        self.assertEqual(outcomes.comparison_view(trimmed, None)["arms"]["A5"]["cost_steps_mean"],
                         "NOT_MEASURED")

    def test_diagnosis_panel_separates_abstain_incomplete_and_denial(self) -> None:
        panel = self.view["diagnosis"]["by_arm"]
        self.assertGreater(panel["A5"]["safe_abstain"], 0)
        self.assertGreater(panel["A5"]["incomplete"], 0)
        self.assertIn("policy_denial", panel["A5"])

    def test_replay_is_labelled_hypothetical_never_a_verified_cause(self) -> None:
        replay = self.view["replay"]
        self.assertTrue(replay["label"].startswith("HYPOTHETICAL_REPLAY"))
        self.assertEqual(replay["physical_causality"], "NOT_ESTABLISHED")
        self.assertNotIn("verified cause", json.dumps(replay).replace("not a verified", ""))

    def test_no_model_free_result_gets_a_real_agent_badge(self) -> None:
        self.assertEqual(self.view["provenance"]["badge"], "scripted")
        self.assertEqual(outcomes.provenance({"evidence_type": "local_model"}, {})["badge"],
                         "unlabelled")
        self.assertEqual(outcomes.provenance({"evidence_type": "local_model"},
                                             {"model": {"digest": "sha256:abc"}})["badge"],
                         "real-agent")
        for key in ("source_sha", "model_digest", "population", "seeds"):
            self.assertIn(key, self.view["provenance"])

    def test_budgets_and_red_team_hold_no_secrets_and_no_controls(self) -> None:
        outcomes.assert_content_safe(self.view)
        self.assertEqual(self.view["budgets"]["queue_depth"], "NOT_MEASURED")
        self.assertEqual(self.view["red_team"]["controls"], [])
        scenarios = [s["scenario"] for s in self.view["red_team"]["scenarios"]]
        for needle in ("contaminated evidence", "revoked principal", "erased memory"):
            self.assertTrue(any(needle in s for s in scenarios), needle)
        with self.assertRaises(ValueError):
            outcomes.assert_content_safe({"rows": [{"prompt": "x"}]})

    def test_lineage_never_counts_copies_as_independent(self) -> None:
        fabric = MemoryFabric(":memory:", auto_activate=True)
        self.addCleanup(fabric.close)
        origin = fabric.remember("a", "pump 4 limit 9 bar", scope="team")
        fabric.retrieve("b", "pump 4 limit", k=3)
        copy = fabric.remember("b", "pump 4 limit 9 bar", scope="team")
        rows = outcomes.lineage_view(fabric, [origin, copy])
        self.assertEqual({r["independent_roots_with_copies"] for r in rows}, {1})
        self.assertTrue(all(r["independent_endorsement"] is False for r in rows))
        self.assertTrue(all(r["version"] == 1 and r["trust_state"] for r in rows))


class ServedReadOnly(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory()
        write_artifacts(Path(cls.tmp.name))
        cls.fabric = MemoryFabric(":memory:", auto_activate=True)
        cls.memory = cls.fabric.remember("a", "pump 4 limit 9 bar", scope="team")
        cls.patch = mock.patch.dict(os.environ, {"MEMORY_FABRIC_OUTCOME_ARTIFACTS": cls.tmp.name})
        cls.patch.start()
        cls.server = build_server(cls.fabric, host="127.0.0.1", port=0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.patch.stop()
        cls.fabric.close()
        cls.tmp.cleanup()

    def get(self, path: str):
        with urllib.request.urlopen(self.base + path, timeout=10) as response:
            return response.status, response.read().decode("utf-8")

    def test_the_view_and_the_page_are_served(self) -> None:
        status, body = self.get("/api/agent-outcomes")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["schema_id"], outcomes.SCHEMA_ID)
        status, page = self.get("/agent-outcomes.html")
        self.assertEqual(status, 200)
        status, lineage = self.get(f"/api/agent-outcomes/lineage?id={self.memory}")
        self.assertEqual(json.loads(lineage)[0]["memory_id"], self.memory)

    def test_the_page_has_no_control_that_could_write(self) -> None:
        page = (ROOT / "src/memory_fabric/observability/static/agent-outcomes.html").read_text()
        self.assertNotRegex(page, r"(?i)<form|<button|method:\s*\"(POST|PUT|PATCH|DELETE)\"")
        self.assertEqual(re.findall(r'method:\s*"(\w+)"', page), ["GET"])

    def test_writes_are_refused_and_change_nothing(self) -> None:
        before = len(self.fabric.log)
        for method in ("POST", "PUT", "DELETE"):
            request = urllib.request.Request(self.base + "/api/agent-outcomes", data=b"{}",
                                             method=method)
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(request, timeout=10)
            self.assertEqual(caught.exception.code, HTTPStatus.METHOD_NOT_ALLOWED)
        self.assertEqual(len(self.fabric.log), before)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

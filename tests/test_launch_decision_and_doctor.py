"""Launch decision rules (W24-03, W24-10) and the troubleshooting command (W20-10)."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"_{name}", ROOT / "tools" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


launch = _load("launch_decision")
doctor = _load("agent_outcome_doctor")
gate_tool = _load("agent_outcome_end_to_end_gate")
SHA = "d" * 40


def gate(status="PASS", synthetic="SCRIPTED_PASS", **positive):
    rows = [{"gate_id": "synthetic_outcome_gate", "status": synthetic}]
    rows += [{"gate_id": g, "status": positive.get(g, "NOT_RUN")}
             for g in ("confirmatory", "real_agent", "model_attacks", "independent_review")]
    return {"status": status, "candidate_commit_sha": SHA, "release_matrix": {"rows": rows}}


def card(a3: float, a5: float):
    return {"arms": {"A3": {"safe_success": {"value": a3}}, "A5": {"safe_success": {"value": a5}}}}


ABLATION = {"headroom": {"improvable_over_a3": 8}}


class Decision(unittest.TestCase):
    def test_scripted_evidence_gives_engineering_go_and_deployment_hold(self) -> None:
        record = launch.decide(gate(), card(0.4, 0.6), ABLATION, {"BLOCKED_EXTERNAL": 8}, ["draft"])
        self.assertEqual(record["engineering"]["decision"], "GO")
        self.assertEqual(record["deployment"]["decision"], "HOLD")
        self.assertTrue(any("real_agent" in r for r in record["deployment"]["reasons"]))

    def test_a_failed_gate_holds_engineering(self) -> None:
        record = launch.decide(gate(status="FAIL", synthetic="FAILED"), card(0.4, 0.6), ABLATION, {}, [])
        self.assertEqual(record["engineering"]["decision"], "HOLD")

    def test_a_fair_baseline_that_ties_is_no_go(self) -> None:
        record = launch.decide(gate(), card(0.6, 0.6), ABLATION, {}, [])
        self.assertEqual(record["deployment"]["decision"], "NO_GO")

    def test_no_headroom_is_no_go(self) -> None:
        record = launch.decide(gate(), card(0.4, 0.6), {"headroom": {"improvable_over_a3": 0}}, {}, [])
        self.assertEqual(record["deployment"]["decision"], "NO_GO")

    def test_deployment_go_needs_every_gate_of_its_own_type(self) -> None:
        full = gate(confirmatory="CONFIRMATORY_SUPPORTED", real_agent="LOCAL_MODEL_PASS",
                    model_attacks="LOCAL_MODEL_PASS", independent_review="PASS")
        self.assertEqual(launch.decide(full, card(0.4, 0.6), ABLATION, {}, [])["deployment"]["decision"],
                         "GO")
        partial = gate(confirmatory="CONFIRMATORY_SUPPORTED", real_agent="LOCAL_MODEL_PASS")
        self.assertEqual(launch.decide(partial, card(0.4, 0.6), ABLATION, {}, [])["deployment"]["decision"],
                         "HOLD")

    def test_the_record_hashes_its_inputs(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "d.json"
            gate_path = Path(directory) / "gate.json"
            gate_path.write_text(json.dumps(gate()))
            self.assertEqual(launch.main(["--gate", str(gate_path), "--out-json", str(out),
                                          "--out-md", str(Path(directory) / "d.md")]), 0)
            record = json.loads(out.read_text())
        self.assertEqual(set(record["inputs"]), {"gate", "scorecard", "ablation", "ledger",
                                                 "registration"})
        self.assertTrue(all(len(item["sha256"]) == 64 for item in record["inputs"].values()))


class NoOverclaimedIntegrity(unittest.TestCase):
    """W19-06: hashes are integrity checks; nothing calls them attestation or certification."""

    WORDS = ("attestation", "attested", "certified", "certification")

    def scrub(self, text: str) -> str:
        for signature in (launch.SIGNATURE, gate_tool.SIGNATURE):
            text = text.replace(signature, "")
        return text.lower()

    def test_reports_say_they_are_unsigned(self) -> None:
        record = launch.decide(gate(), card(0.4, 0.6), ABLATION, {}, [])
        record = {"gate_commit": SHA, "signature": launch.SIGNATURE, **record,
                  "inputs": {"gate": {"path": "g.json", "sha256": "0" * 64}}}
        self.assertTrue(launch.SIGNATURE.startswith("UNSIGNED"))
        self.assertIn(launch.SIGNATURE, launch.render(record))
        report = {"candidate_commit_sha": SHA, "status": "PASS", "stages": {},
                  "release_matrix": gate_tool.build_matrix({}, SHA), "signature": gate_tool.SIGNATURE}
        self.assertIn(gate_tool.SIGNATURE, gate_tool.render_markdown(report))

    def test_no_view_or_report_calls_a_hash_an_attestation(self) -> None:
        texts = {"dashboard": (ROOT / "src/memory_fabric/observability/static/dashboard.html")
                 .read_text(encoding="utf-8")}
        for path in sorted((ROOT / "research/results/agent-outcomes").glob("**/*.md")):
            if "LAUNCH" in path.name or "REPORT" in path.name:
                texts[path.name + str(path.parent.name)] = path.read_text(encoding="utf-8")
        for name, text in texts.items():
            for word in self.WORDS:
                self.assertNotIn(word, self.scrub(text), f"{name} says {word!r}")


class Doctor(unittest.TestCase):
    def test_reports_the_canonical_runtime_roles_and_ledger(self) -> None:
        report = doctor.diagnose()
        self.assertEqual(report["outcome_runtime"]["canonical"], "memory_fabric.outcome_typed")
        self.assertTrue(all(v["deprecated"] for v in report["outcome_runtime"]["legacy"].values()))
        self.assertEqual(report["agent_visibility"]["tools_by_role"]["executor"], ["execute_proposal"])
        self.assertTrue(report["recovery"]["enabled_by_default"])
        self.assertEqual(report["local_model"]["status"], "NOT_CHECKED")
        self.assertIn("by_status", report["ledger"])

    def test_model_check_is_loopback_and_labels_a_fake(self) -> None:
        from benchmarks.fake_local_model import FAKE_MODEL, FakeLocalModelServer

        missing = doctor.diagnose("qwen2.5:1.5b", "http://127.0.0.1:9")["local_model"]
        self.assertEqual(missing["status"], "REAL_AGENT_NOT_RUN")
        self.assertFalse(missing["download_attempted"])
        self.assertEqual(doctor.diagnose("m", "http://example.com")["local_model"]["status"], "REFUSED")
        with FakeLocalModelServer() as host:
            fake = doctor.diagnose(FAKE_MODEL, host)["local_model"]
        self.assertEqual((fake["status"], fake["fake"]), ("MODELS_AVAILABLE", True))

    def test_runs_without_importing_legacy_packages(self) -> None:
        done = subprocess.run([sys.executable, "-W", "error::DeprecationWarning",
                               "tools/agent_outcome_doctor.py", "--json"], cwd=ROOT,
                              capture_output=True, text=True, timeout=120)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout)["schema_id"], doctor.SCHEMA_ID)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

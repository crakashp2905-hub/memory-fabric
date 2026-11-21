"""Checklist W01 tooling: baseline, triage, preflight, inventory, claims and the task ledger."""

from __future__ import annotations

import io
import json
import socket
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import baseline_manifest  # noqa: E402
import checklist_ledger  # noqa: E402
import claim_scanner  # noqa: E402
import classify_workflow_run  # noqa: E402
import evidence_inventory  # noqa: E402
import model_attack_check  # noqa: E402
import model_preflight  # noqa: E402
import status_at_head  # noqa: E402

BASELINE = ROOT / "research" / "results" / "agent-outcomes" / "baseline-70e34c8"


def _no_network(*_args: object, **_kwargs: object) -> None:
    raise AssertionError("a network connection was attempted")


class BaselineManifest(unittest.TestCase):
    def test_build_is_deterministic_and_offline(self) -> None:
        with mock.patch.object(socket.socket, "connect", _no_network):
            first = baseline_manifest.render(baseline_manifest.build())
            second = baseline_manifest.render(baseline_manifest.build())
        self.assertEqual(first, second)
        self.assertEqual(baseline_manifest.verify(json.loads(first)), [])

    def test_round_trip_and_tamper_detection(self) -> None:
        manifest = baseline_manifest.build()
        reloaded = json.loads(baseline_manifest.render(manifest))
        self.assertEqual(reloaded, manifest)
        reloaded["python"]["version"] = "2.7.0"
        self.assertIn("manifest_sha256 does not match the manifest body",
                      baseline_manifest.verify(reloaded))

    def test_committed_baseline_pins_the_clean_starting_commit(self) -> None:
        stored = json.loads((BASELINE / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(baseline_manifest.verify(stored), [])
        self.assertEqual(stored["source"]["commit_sha"], "70e34c870d387cb5de8ba0bbdda0320cf3574d6c")
        self.assertTrue(stored["source"]["tree_clean"])
        self.assertEqual(stored["network_calls"], 0)
        self.assertEqual(stored["package"]["version"], "0.19.0")


class BaselineRecord(unittest.TestCase):
    def test_every_baseline_entry_points_at_an_existing_path_with_a_known_status(self) -> None:
        from memory_fabric.outcome_typed.evidence import OutcomeEvidenceStatus

        record = json.loads((BASELINE / "baseline.json").read_text(encoding="utf-8"))
        allowed = {status.value for status in OutcomeEvidenceStatus}
        self.assertEqual(record["overall_status"], "NOT_RUN")
        for section in ("known_results", "known_failures", "not_run"):
            self.assertTrue(record[section], section)
            for entry in record[section]:
                with self.subTest(entry=entry["id"]):
                    self.assertIn(entry["status"], allowed)
                    self.assertTrue((ROOT / entry["path"]).exists(), entry["path"])
        self.assertTrue(any("production" in warning for warning in record["warnings"]))


class WorkflowTriage(unittest.TestCase):
    def test_stored_model_attack_failure_is_no_runner_not_a_vulnerability(self) -> None:
        record = json.loads((BASELINE / "model-attacks-run-43848470357.json").read_text(
            encoding="utf-8"))
        result = classify_workflow_run.classify(record)
        self.assertEqual(result["failure_class"], "NO_RUNNER_ASSIGNED")
        self.assertEqual(result["root_cause"], "CAUSE_UNVERIFIED")
        self.assertEqual(result["invariant_status"], "NOT_RUN")
        stored = json.loads((BASELINE / "model-attacks-run-43848470357.classification.json")
                            .read_text(encoding="utf-8"))
        self.assertEqual(stored, result)

    def test_step_failures_are_classified_by_stage(self) -> None:
        def record(step: str) -> dict:
            return {"run": {"id": 1, "conclusion": "failure"},
                    "jobs": [{"id": 2, "conclusion": "failure", "runner_id": 7, "runner_name": "r",
                              "steps": [{"number": 1, "name": "checkout", "conclusion": "success"},
                                        {"number": 2, "name": step, "conclusion": "failure"}]}]}
        cases = {"Install and start Ollama": "SETUP_STEP_FAILED",
                 "python -m experiments.g4b_conflicts": "EXPERIMENT_STEP_FAILED",
                 "tools/model_attack_check.py": "INVARIANT_CHECK_FAILED"}
        for step, expected in cases.items():
            with self.subTest(step=step):
                self.assertEqual(classify_workflow_run.classify(record(step))["failure_class"],
                                 expected)
        self.assertEqual(classify_workflow_run.classify(
            {"run": {"conclusion": "success"}, "jobs": []})["failure_class"], "PASSED")


class ModelAttackCheck(unittest.TestCase):
    def write(self, directory: str, name: str, fabric: float, mechanism: float) -> Path:
        path = Path(directory) / name
        path.write_text(json.dumps({"experiment": "t2b-notice", "no_arm_beats_the_oracle": True,
                                    "arms": {"fabric": {"safe_success": fabric, "acted_on_invalid": 0.1},
                                             "fabric_notice": {"safe_success": mechanism,
                                                               "acted_on_invalid": 0.0},
                                             "shared_store": {"safe_success": 0.2,
                                                              "acted_on_invalid": 0.3}}}),
                        encoding="utf-8")
        return path

    def test_missing_runtime_is_model_not_available_never_pass(self) -> None:
        with TemporaryDirectory() as directory:
            missing = Path(directory) / "g4b.json"
            report = model_attack_check.classify(
                [missing], {"status": "REAL_AGENT_NOT_RUN", "reason": "LOCAL_RUNTIME_UNAVAILABLE"})
            self.assertEqual(report["status"], "MODEL_NOT_AVAILABLE")
            self.assertEqual(model_attack_check.exit_code(report["status"]), 2)
            report = model_attack_check.classify(
                [missing], {"status": "MODELS_AVAILABLE", "models": []})
            self.assertEqual(report["status"], "NOT_RUN")

    def test_invariant_failure_and_pass(self) -> None:
        with TemporaryDirectory() as directory:
            bad = self.write(directory, "bad.json", fabric=0.6, mechanism=0.3)
            good = self.write(directory, "good.json", fabric=0.6, mechanism=0.7)
            self.assertEqual(model_attack_check.classify([bad])["status"], "FAIL")
            self.assertEqual(model_attack_check.classify([good])["status"], "PASS")
            status_out = Path(directory) / "status.json"
            with redirect_stdout(io.StringIO()):
                code = model_attack_check.main(["--status-out", str(status_out), str(good),
                                                str(Path(directory) / "absent.json")])
            self.assertEqual(code, 2)
            self.assertEqual(json.loads(status_out.read_text())["status"], "NOT_RUN")

    def test_positional_usage_still_works(self) -> None:
        with TemporaryDirectory() as directory:
            good = self.write(directory, "good.json", fabric=0.6, mechanism=0.7)
            with redirect_stdout(io.StringIO()):
                self.assertEqual(model_attack_check.main([str(good)]), 0)


class FakeClient:
    def __init__(self, models: list[dict], fail: bool = False) -> None:
        self.models, self.fail = models, fail

    def inventory(self) -> list[dict]:
        if self.fail:
            raise model_preflight.OllamaError("down")
        return self.models


class ModelPreflight(unittest.TestCase):
    def test_non_loopback_host_is_refused_before_connecting(self) -> None:
        with mock.patch("urllib.request.urlopen", side_effect=AssertionError("connected")):
            for host in ("http://example.com:11434", "http://10.0.0.5:11434", "ftp://127.0.0.1"):
                with self.subTest(host=host), self.assertRaises(model_preflight.NonLocalHostError):
                    model_preflight.preflight(host)
        self.assertEqual(model_preflight.require_loopback("http://127.0.0.2:1/"), "http://127.0.0.2:1")

    def test_absent_runtime_or_model_is_not_run(self) -> None:
        down = model_preflight.preflight(required=["qwen2.5:1.5b"], client=FakeClient([], fail=True))
        self.assertEqual((down["status"], down["reason"]),
                         ("REAL_AGENT_NOT_RUN", "LOCAL_RUNTIME_UNAVAILABLE"))
        self.assertFalse(down["download_attempted"])
        self.assertFalse(down["scripted_substitute_used"])
        other = FakeClient([{"name": "llama3.2:3b", "digest": "d1", "details": {}}])
        missing = model_preflight.preflight(required=["qwen2.5:1.5b"], client=other)
        self.assertEqual(missing["reason"], "PINNED_MODEL_NOT_INSTALLED")
        undigested = FakeClient([{"name": "qwen2.5:1.5b", "digest": None, "details": {}}])
        self.assertEqual(model_preflight.preflight(required=["qwen2.5:1.5b"],
                                                   client=undigested)["reason"],
                         "MODEL_DIGEST_UNAVAILABLE")

    def test_installed_model_is_inventoried_with_digest(self) -> None:
        client = FakeClient([{"name": "qwen2.5:1.5b", "digest": "abc", "size": 1,
                              "details": {"quantization_level": "Q4_K_M", "parameter_size": "1.5B",
                                          "family": "qwen2"}}])
        report = model_preflight.preflight(required=["qwen2.5:1.5b"], client=client)
        self.assertEqual(report["status"], "MODELS_AVAILABLE")
        self.assertEqual(report["models"][0]["quantization"], "Q4_K_M")

    def test_committed_preflight_records_this_environment_honestly(self) -> None:
        stored = json.loads((BASELINE / "model-preflight.json").read_text(encoding="utf-8"))
        self.assertEqual(stored["status"], "REAL_AGENT_NOT_RUN")
        self.assertFalse(stored["download_attempted"])


class CurrentStateVersions(unittest.TestCase):
    def test_current_tree_has_no_current_state_contradictions(self) -> None:
        self.assertEqual(status_at_head.current_state_mentions(status_at_head.versions()), [])

    def test_stale_current_state_statements_are_detected(self) -> None:
        stale = {"docs/AGENT_OUTCOME_EVALUATION.md":
                 "package is version `0.19.0`; the event schema\nand `SPEC.md` remain at `0.14.0`.",
                 "deploy/helm/memory-fabric/Chart.yaml": 'appVersion: "0.14.0"',
                 "docs/MEMORY_FABRIC_RELEASE_CHECKLIST.md": "dist/memory-fabric-0.14.0-py3-none-any.whl"}

        def read(rel: str) -> str:
            return stale.get(rel) or (ROOT / rel).read_text(encoding="utf-8")

        found = status_at_head.current_state_mentions(status_at_head.versions(), read)
        self.assertEqual(len(found), 3, found)


class EvidenceInventory(unittest.TestCase):
    def test_every_promoted_claim_resolves_its_commitments(self) -> None:
        data = evidence_inventory.build()
        self.assertTrue(data["promoted_complete"], [c["problems"] for c in data["promoted_claims"]])
        statuses = {row["status"] for row in data["results"]}
        self.assertLessEqual(statuses, {"PROMOTED", "RECORDED_WITH_COMMIT", "LEGACY_UNVERIFIED"})
        self.assertGreater(data["result_status_counts"]["LEGACY_UNVERIFIED"], 0)

    def test_changed_evidence_or_unresolvable_commit_is_incomplete(self) -> None:
        registry = json.loads((ROOT / "research" / "claims.json").read_text(encoding="utf-8"))
        claim = dict(registry["claims"][0], expected_evidence_sha256="0" * 64)
        self.assertEqual(evidence_inventory.claim_commitments(claim)["status"], "PROMOTED_INCOMPLETE")
        short = next(c for c in registry["claims"] if c["id"] == "http-50-client")
        broken = {key: value for key, value in short.items() if key != "resolved_commit"}
        result = evidence_inventory.claim_commitments(broken)
        self.assertIn("unresolved commitment: source_commit", result["problems"])

    def test_committed_inventory_is_current(self) -> None:
        self.assertEqual(evidence_inventory.OUT.read_text(encoding="utf-8"),
                         evidence_inventory.render(),
                         "regenerate: python tools/evidence_inventory.py --write")


class ClaimScanner(unittest.TestCase):
    def test_current_documents_have_no_unsupported_outcome_numbers(self) -> None:
        report = claim_scanner.scan()
        self.assertEqual(report["unsupported"], [])
        self.assertGreater(len(report["claims"]), 0)

    def test_unsupported_number_fails_and_evidence_link_passes(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "docs").mkdir()
            (root / "research" / "results").mkdir(parents=True)
            (root / "research" / "results" / "r.json").write_text("{}", encoding="utf-8")
            doc = root / "docs" / "AGENT_OUTCOME_EVALUATION.md"
            doc.write_text("A5 raised task success to 84% on held-out cases.\n", encoding="utf-8")
            self.assertEqual(claim_scanner.scan(root, [])["status"], "FAIL")
            doc.write_text("A5 raised task success to 84% "
                           "([raw](../research/results/r.json)).\n", encoding="utf-8")
            self.assertEqual(claim_scanner.scan(root, [])["status"], "PASS")
            doc.write_text("Released 0.19.0 with the d4fd174 success fix.\n", encoding="utf-8")
            self.assertEqual(claim_scanner.scan(root, [])["claims"], [])

    def test_allowlist_entries_need_text_reason_and_date(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "allow.json"
            path.write_text(json.dumps({"entries": [{"file": "README.md", "contains": "84%"}]}))
            with self.assertRaises(ValueError):
                claim_scanner.load_allowlist(path)
            path.write_text(json.dumps({"entries": [{"file": "README.md", "contains": "84%",
                                                     "reason": "r", "date": "not-a-date"}]}))
            with self.assertRaises(ValueError):
                claim_scanner.load_allowlist(path)
        self.assertEqual(claim_scanner.load_allowlist(), [])


class TaskLedger(unittest.TestCase):
    def setUp(self) -> None:
        self.spec = checklist_ledger.parse_spec()
        self.ledger = checklist_ledger.load()

    def test_spec_has_240_tasks_with_acceptance(self) -> None:
        self.assertEqual(len(self.spec["tasks"]), 240)
        self.assertEqual(len(self.spec["workstreams"]), 24)
        self.assertTrue(all(task["acceptance"] for task in self.spec["tasks"].values()))

    def test_committed_ledger_is_valid_and_page_current(self) -> None:
        self.assertEqual(checklist_ledger.validate(self.ledger, self.spec), [])
        self.assertEqual(checklist_ledger.PAGE.read_text(encoding="utf-8"),
                         checklist_ledger.render(self.ledger, self.spec))

    def _with(self, task_id: str, entry: dict) -> list[str]:
        ledger = json.loads(json.dumps(self.ledger))
        ledger["tasks"][task_id] = entry
        return checklist_ledger.validate(ledger, self.spec)

    def test_statuses_the_evidence_cannot_carry_are_refused(self) -> None:
        test = "tests/test_agent_validation_w01.py"
        sha = "70e34c870d387cb5de8ba0bbdda0320cf3574d6c"
        self.assertTrue(self._with("W01-01", {"status": "IMPLEMENTED"}))
        self.assertTrue(self._with("W01-01", {"status": "IMPLEMENTED", "evidence": ["no/such/file"]}))
        self.assertTrue(self._with("W01-01", {"status": "TESTED", "evidence": ["tools/baseline_manifest.py"],
                                              "tests": [test]}))
        self.assertTrue(self._with("W01-01", {"status": "TESTED", "evidence": ["tools/baseline_manifest.py"],
                                              "tests": ["test_x"], "verified_sha": sha}))
        self.assertTrue(self._with("W01-01", {"status": "SCRIPTED_QUALIFIED",
                                              "evidence": ["tools/baseline_manifest.py"],
                                              "tests": [test], "verified_sha": sha}))
        self.assertTrue(self._with("W12-05", {"status": "LOCAL_MODEL_QUALIFIED",
                                              "evidence": ["research/results/agent-outcomes/baseline-70e34c8/model-preflight.json",
                                                           "research/checklist/gate.json"],
                                              "tests": [test], "verified_sha": sha}))
        self.assertTrue(self._with("W24-09", {"status": "BLOCKED_EXTERNAL"}))
        self.assertTrue(self._with("W01-01", {"status": "PASSED"}))
        self.assertTrue(self._with("W01-01", {"status": "TODO", "extra": 1}))
        self.assertEqual(self._with("W01-01", {"status": "TESTED",
                                               "evidence": ["tools/baseline_manifest.py"],
                                               "tests": [test], "verified_sha": sha}), [])
        self.assertEqual(self._with("W24-09", {"status": "BLOCKED_EXTERNAL",
                                               "blocked_on": "an independent pilot partner"}), [])

    def test_spec_drift_and_missing_tasks_are_refused(self) -> None:
        ledger = json.loads(json.dumps(self.ledger))
        ledger["spec_sha256"] = "0" * 64
        del ledger["tasks"]["W24-10"]
        problems = checklist_ledger.validate(ledger, self.spec)
        self.assertTrue(any("different revision" in p for p in problems))
        self.assertTrue(any("missing from the ledger" in p for p in problems))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

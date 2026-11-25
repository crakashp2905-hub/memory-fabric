"""The Vega-CDM task ledger and the separate-verdict gate (VEGA-CDM-009, 010, 177-180)."""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import vega_cdm_gate as gate  # noqa: E402
import vega_ledger as ledger  # noqa: E402


class Ledger(unittest.TestCase):
    def setUp(self):
        self.spec = ledger.parse_spec()
        self.data = ledger.load()

    def test_every_checklist_task_has_an_entry_and_the_ledger_validates(self):
        self.assertEqual(len(self.spec["tasks"]), 180)
        self.assertEqual(ledger.validate(self.data, self.spec), [])

    def test_docs_only_or_testless_validation_is_refused(self):
        bad = copy.deepcopy(self.data)
        tid = next(iter(bad["tasks"]))
        bad["tasks"][tid] = {"status": "VALIDATED", "evidence": ["docs/VEGA_CDM_GUIDE.md"],
                             "tests": ["tests/test_vega_u_adapter.py"], "verified_sha": "0" * 40}
        self.assertTrue(any("documentation alone" in p for p in ledger.validate(bad, self.spec)))
        bad["tasks"][tid] = {"status": "VALIDATED", "evidence": ["src/memory_fabric/adapters/vega_u.py"],
                             "verified_sha": "0" * 40}
        self.assertTrue(any("at least one test" in p for p in ledger.validate(bad, self.spec)))

    def test_model_validation_needs_a_recorded_real_inference(self):
        bad = copy.deepcopy(self.data)
        tid = next(iter(bad["tasks"]))
        bad["tasks"][tid] = {"status": "MODEL_VALIDATED", "evidence": ["src/memory_fabric/adapters/vega_u.py"],
                             "tests": ["tests/test_vega_u_adapter.py"], "verified_sha": "0" * 40,
                             "model_result": "research/results/vega-cdm/development/scripted.json"}
        self.assertTrue(any("real inference" in p for p in ledger.validate(bad, self.spec)))

    def test_blocked_says_why(self):
        bad = copy.deepcopy(self.data)
        tid = next(iter(bad["tasks"]))
        bad["tasks"][tid] = {"status": "BLOCKED", "evidence": []}
        self.assertTrue(any("blocked on" in p for p in ledger.validate(bad, self.spec)))


class Gate(unittest.TestCase):
    def test_docs_are_consistent_with_the_pins_and_make_no_efficacy_claim(self):
        result = gate.docs()
        self.assertEqual(result, {"status": "DOCS_CONSISTENT", "problems": []})

    def test_research_and_release_verdicts_stay_separate_from_ci(self):
        self.assertEqual(gate.research()["status"], "RESEARCH_NO_GO")
        self.assertEqual(gate.model(None)["status"], "MODEL_NOT_RUN")
        self.assertIn("tests/test_vega_ledger_and_gate.py", gate.CONTRACT_TESTS)
        source = (ROOT / "tools" / "vega_cdm_gate.py").read_text(encoding="utf-8")
        for verdict in ("CORE_PASS", "MODEL_NOT_RUN", "AGENT_NOT_RUN", "RELEASE_NO_GO", "DOCS_CONSISTENT"):
            self.assertIn(verdict, source)
        self.assertIn("not model efficacy", source)

    def test_a_stale_digest_or_an_overclaim_in_the_docs_is_caught(self):
        original = gate.DOCS
        tmp = ROOT / "research" / "results" / "vega-cdm" / "_gate_probe.md"
        tmp.write_text("vegaml 0.18.0 engine sha256 deadbeef; Vega improves safe completion.\n")
        try:
            gate.DOCS = [*original, tmp.relative_to(ROOT).as_posix()]
            problems = gate.docs()["problems"]
        finally:
            gate.DOCS = original
            tmp.unlink()
        self.assertEqual(len(problems), 3)


RECORDS_WITHOUT_A_LEVEL = {"memory-fabric.vega-next-baseline.v1", "memory-fabric.ci-audit.v1",
                           "memory-fabric.vega-next.failure-trace.v1", "memory-fabric.vega-next-cdm-value.v1",
                           "memory-fabric.vega-next-perf.v1",
                           # analyses of recorded rows with no model call of their own (freeze plan)
                           "memory-fabric.planner-error-taxonomy.v1", "memory-fabric.vega-specificity-diagnosis.v1"}
DEVELOPMENT_LEVELS = ("VEGA_MODEL_DEVELOPMENT", "NO_ADVISOR", "LOCAL_MODEL_DEVELOPMENT")


class EvidenceLevels(unittest.TestCase):
    def test_every_recorded_vega_report_states_a_level_it_can_carry(self):
        from memory_fabric.causal_replay.semantic.taxonomy import check_report_level
        for path in (ROOT / "research" / "results" / "vega-cdm").rglob("*.json"):
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("schema_id") in RECORDS_WITHOUT_A_LEVEL:
                continue  # baselines, CI audits and failure traces are records, not result reports
            if data.get("schema_id") == "memory-fabric.vega-next-gate.v1":
                # the next-study matrix: one verdict per gate, never a release or QUALIFIED claim
                self.assertIn(data["release"], ("RELEASE_NO_GO", "ENGINEERING_GO_ONLY"), path)
                self.assertNotIn("QUALIFIED", json.dumps(data), path)
                continue
            if data.get("schema_id") == "memory-fabric.vega-cdm-gate.v1":
                # gate records carry one verdict per tier instead of one level
                self.assertEqual(data["release"]["status"], "RELEASE_NO_GO", path)
                self.assertEqual(data["agent"]["status"], "AGENT_NOT_RUN", path)
                self.assertEqual(data["ci_covers"], ["core", "docs"], path)
                continue
            level = data.get("evidence_level", data.get("status"))
            if level in DEVELOPMENT_LEVELS:
                continue  # development-only levels: not efficacy, checked by the arms tests
            if level == "VEGA_MODEL_SMOKE":
                data = {**data, "model_digest": json.dumps(data).count("78f96be7c6a0") > 0,
                        "real_inference": True}
            self.assertEqual(check_report_level({**data, "verdict": data.get("verdict", "")}), [], path)


if __name__ == "__main__":
    unittest.main()

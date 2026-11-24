"""Semantic recovery advice in the canonical outcome runtime (VEGA S09)."""

from __future__ import annotations

import json
import unittest

from benchmarks.outcome_arms import build_task
from benchmarks.outcome_episode import ScriptedTeam
from memory_fabric import MemoryFabric
from memory_fabric.causal_replay.semantic.scripted import ScriptedAdvisor
from memory_fabric.outcome_typed import semantic_advisory as sa
from memory_fabric.outcome_typed.api import OutcomeAPI
from memory_fabric.outcome_typed.episode import AgentStep


def blocked(mode: str, advisor=None):
    """A task the runtime blocks for its own reason: the actor asks for an undeclared tool."""
    task = build_task("public_correction", 0)

    def bad(role, observation):
        step = ScriptedTeam()(role, observation)
        if role == "planner" and step.intent == "retrieve":
            return AgentStep(observation.task_id, role, step.step_id, "retrieve", {"tool": "delete_everything"})
        return step

    fabric = MemoryFabric(":memory:", auto_activate=True)
    api = OutcomeAPI(fabric, effects={"set_target": task.world.effect("set_target")}, team=bad,
                     semantic_advisor=advisor, semantic_mode=mode)
    result = api.run_task({"task_id": task.envelope.task_id, "objective": "set the actuator"},
                          feed=task.world.feed)
    return api, result, fabric


class Modes(unittest.TestCase):
    def test_off_is_the_default_and_byte_identical_and_calls_nothing(self):
        advisor = ScriptedAdvisor()
        plain, r1, f1 = blocked("OFF")
        off, r2, f2 = blocked("OFF", advisor)
        self.addCleanup(f1.close)
        self.addCleanup(f2.close)
        self.assertEqual(json.dumps(plain.inspect_failure(r1.task_id), sort_keys=True),
                         json.dumps(off.inspect_failure(r2.task_id), sort_keys=True))
        self.assertEqual(advisor.calls, 0)
        fabric = MemoryFabric(":memory:", auto_activate=True)
        self.addCleanup(fabric.close)
        task = build_task("public_correction", 0)
        self.assertEqual(OutcomeAPI(fabric, effects={"set_target": task.world.effect("set_target")}).semantic_mode,
                         "OFF")

    def test_shadow_logs_without_changing_output_and_qualified_is_refused(self):
        advisor = ScriptedAdvisor()
        plain, r1, f1 = blocked("OFF")
        shadow, r2, f2 = blocked("SHADOW", advisor)
        self.addCleanup(f1.close)
        self.addCleanup(f2.close)
        self.assertEqual(plain.inspect_failure(r1.task_id), shadow.inspect_failure(r2.task_id))
        self.assertEqual(len(shadow.semantic_shadow_log), 1)
        for mode in ("QUALIFIED", "ON", "auto"):
            with self.subTest(mode=mode), self.assertRaises(sa.AdvisoryConfigError):
                sa.check_mode(mode)

    def test_advisory_adds_a_catalog_proposal_but_never_rewrites_the_cause(self):
        advisor = ScriptedAdvisor({"next_step": {"choice": "replan", "probs": {
            "refresh": 0.05, "re_retrieve": 0.1, "inspect_provenance": 0.05, "ask": 0.05, "replan": 0.7,
            "abstain": 0.05}, "prediction_set": ["replan"], "abstain": False}})
        api, result, fabric = blocked("ADVISORY", advisor)
        self.addCleanup(fabric.close)
        out = api.inspect_failure(result.task_id)
        self.assertEqual(out["failure"], "tool")
        advice = out["semantic_advisory"]
        self.assertEqual(advice["cause"], "IRRELEVANT")
        self.assertEqual((advice["status"], advice["step"], advice["kind"]), ("PROPOSED", "REPLAN", "MODEL_PROPOSAL"))
        self.assertIsNone(advice["grants"])
        self.assertTrue(set(advice["ranked"]) <= set(sa.RECOVERY_CATALOG))

    def test_off_catalog_malformed_or_unavailable_advice_is_discarded(self):
        for raw in ({"choice": "grant_admin", "probs": {"grant_admin": 1.0}, "abstain": False},
                    {"garbage": True}):
            with self.subTest(raw=raw):
                api, result, fabric = blocked("ADVISORY", ScriptedAdvisor({"next_step": raw}))
                self.addCleanup(fabric.close)
                self.assertEqual(api.inspect_failure(result.task_id)["semantic_advisory"]["status"], "UNAVAILABLE")

    def test_every_runtime_diagnosis_maps_to_one_authoritative_cause(self):
        from memory_fabric.outcome_typed.api import NEXT_STEPS
        for code in NEXT_STEPS:
            self.assertIn(sa.failure_cause(code), sa.FAILURE_CAUSES)
        self.assertIsNone(sa.failure_cause(None))


if __name__ == "__main__":
    unittest.main()

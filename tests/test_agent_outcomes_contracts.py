"""Contract coverage for truth-free experimental agent outcomes."""

from __future__ import annotations

import hashlib

import unittest

from benchmarks.outcome_report import canonical_report, zero_event_upper_bound
from memory_fabric.agent_outcomes import (
    AgentObservation, AgentStep, EpisodeOutcome, RecoveryEpisode, RecoveryStatus,
)


class TestOutcomeContracts(unittest.TestCase):
    def test_observation_canonical_roundtrip_and_digest(self) -> None:
        observation = AgentObservation("task-1", "Check the current reading.",
                                       ({"source": "sensor", "value": "normal"},),
                                       ("retrieve", "inspect"), {"steps": 4})
        restored = AgentObservation.from_json(observation.canonical_json())
        self.assertEqual(restored, observation)
        self.assertEqual(restored.request_digest(), observation.request_digest())
        self.assertEqual(len(observation.request_digest()), 64)

    def test_observation_rejects_oracle_fields_recursively(self) -> None:
        for field in ("truth", "expected_action", "evidence_usable", "reward"):
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, "evaluator-only"):
                    AgentObservation("task-1", "Do task", ({"metadata": {field: True}},), (), {})

    def test_contracts_reject_unknown_fields_and_unbounded_payloads(self) -> None:
        with self.assertRaisesRegex(ValueError, "fields do not match"):
            AgentObservation.from_json('{"schema_id":"memory-fabric.agent-outcomes.v1",'
                                       '"task_id":"x","instruction":"x","visible_events":[],'
                                       '"permitted_tools":[],"budget":{},"truth":1}')
        with self.assertRaisesRegex(ValueError, "size limit"):
            AgentObservation("task-1", "x", ({"data": "x" * 70_000},), (), {})

    def test_step_rejects_unknown_intent_and_oracle_argument(self) -> None:
        with self.assertRaises(ValueError):
            AgentStep("task-1", "planner", "step-1", "execute", {}, ())
        with self.assertRaisesRegex(ValueError, "evaluator-only"):
            AgentStep("task-1", "planner", "step-1", "propose", {"reward": 1}, ())

    def test_episode_outcome_requires_opaque_oracle_digest(self) -> None:
        good = EpisodeOutcome("task-1", "A5", 1, False, 0, 0, 1, 1, 0, 0, 0, 1.0,
                              hashlib.sha256(b"sealed outcome").hexdigest())
        self.assertIn('"population":"SCRIPTED_AGENT"', canonical_report([good]))
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            EpisodeOutcome("task-1", "A5", 1, True, 0, 0, 0, 0, 0, 0, 0, 1.0, "truth")

    def test_recovery_episode_is_bounded_and_terminal(self) -> None:
        episode = RecoveryEpisode("task-1")
        self.assertTrue(episode.record("evidence_blocked", {"reason": "stale"}))
        self.assertIs(episode.status, RecoveryStatus.BLOCKED)
        self.assertTrue(episode.record("replan"))
        self.assertEqual(episode.recoveries, 1)
        self.assertTrue(episode.record("abstain"))
        self.assertIs(episode.status, RecoveryStatus.ABSTAINED)
        self.assertFalse(episode.record("replan"))

    def test_zero_event_bound_is_not_zero_risk(self) -> None:
        bound = zero_event_upper_bound(0, 20)
        self.assertAlmostEqual(bound, 0.139108, delta=1e-6)
        self.assertAlmostEqual(zero_event_upper_bound(1, 20), 0.216106, delta=1e-6)

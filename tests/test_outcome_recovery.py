"""Versioned request, digest, and recovery-trace compatibility contracts."""

from __future__ import annotations

import hashlib
import json
import unittest

from memory_fabric.agent_outcomes import AgentObservation, AgentStep, RecoveryAction, RecoveryEpisode


class TestVersionedOutcomeRequests(unittest.TestCase):
    def test_observation_json_roundtrip_and_request_digest_are_deterministic(self) -> None:
        first = AgentObservation.from_json(
            '{"schema_id":"memory-fabric.agent-outcomes.v3",'
            '"task_id":"request-1","instruction":"Private prompt canary",'
            '"visible_events":[{"z":2,"a":{"second":false,"first":1}}],'
            '"permitted_tools":["inspect","retrieve"],"budget":{"steps":4}}'
        )
        second = AgentObservation.from_json(
            '{"budget":{"steps":4},"permitted_tools":["inspect","retrieve"],'
            '"visible_events":[{"a":{"first":1,"second":false},"z":2}],'
            '"instruction":"Private prompt canary","task_id":"request-1",'
            '"schema_id":"memory-fabric.agent-outcomes.v3"}'
        )

        self.assertEqual(first.schema_id, "memory-fabric.agent-outcomes.v3")
        self.assertEqual(first.canonical_json(), second.canonical_json())
        self.assertEqual(first.request_digest(), second.request_digest())
        self.assertEqual(len(first.request_digest()), 64)
        self.assertNotIn("Private prompt canary", first.request_digest())
        restored = AgentObservation.from_json(first.canonical_json())
        self.assertEqual(restored, first)
        self.assertEqual(restored.canonical_json(), first.canonical_json())

    def test_agent_step_schema_roundtrip_and_hash_cover_the_canonical_request(self) -> None:
        step = AgentStep(
            "request-2", "planner", "step-1", "propose",
            {"tool": "inspect", "parameters": {"z": 2, "a": 1}},
            (("memory-1", 7),),
        )
        restored = AgentStep.from_json(step.canonical_json())
        self.assertEqual(restored, step)
        self.assertEqual(restored.schema_id, "memory-fabric.agent-outcomes.v3")
        self.assertEqual(restored.canonical_json(), step.canonical_json())
        self.assertEqual(restored.request_digest(), step.request_digest())
        self.assertEqual(len(step.request_digest()), 64)
        changed = AgentStep("request-2", "planner", "step-1", "propose",
                            {"tool": "retrieve", "parameters": {"a": 1, "z": 2}},
                            (("memory-1", 7),))
        self.assertNotEqual(step.request_digest(), changed.request_digest())

    def test_unknown_schema_fields_and_security_metadata_fail_closed(self) -> None:
        observation = {
            "schema_id": "memory-fabric.agent-outcomes.v3", "task_id": "request-3",
            "instruction": "Inspect", "visible_events": [], "permitted_tools": [], "budget": {},
        }
        for extra in (
            {"schema_id": "memory-fabric.agent-outcomes.v2"},
            {"security_metadata": {"capability": "future-token"}},
            {"future_field": True},
        ):
            with self.subTest(extra=extra):
                with self.assertRaises(ValueError):
                    AgentObservation.from_json(json.dumps(observation | extra))

        step = {
            "schema_id": "memory-fabric.agent-outcomes.v3", "task_id": "request-3",
            "actor_id": "planner", "step_id": "step-1", "intent": "propose",
            "arguments": {"tool": "inspect"}, "evidence_versions": [],
        }
        for extra in (
            {"schema_id": "memory-fabric.agent-outcomes.v4"},
            {"security_metadata": {"capability": "future-token"}},
            {"future_field": True},
        ):
            with self.subTest(extra=extra):
                with self.assertRaises(ValueError):
                    AgentStep.from_json(json.dumps(step | extra))

        with self.assertRaisesRegex(ValueError, "evaluator-only"):
            AgentStep.from_json(json.dumps(step | {
                "arguments": {"evaluator_capability": "future-token"},
            }))

    def test_ambiguous_json_and_nonfinite_values_are_rejected(self) -> None:
        duplicate = (
            '{"schema_id":"memory-fabric.agent-outcomes.v3",'
            '"task_id":"request-4","task_id":"request-5",'
            '"instruction":"Inspect","visible_events":[],"permitted_tools":[],"budget":{}}'
        )
        with self.assertRaisesRegex(ValueError, "duplicate JSON field"):
            AgentObservation.from_json(duplicate)

        nonfinite = (
            '{"schema_id":"memory-fabric.agent-outcomes.v3",'
            '"task_id":"request-4","instruction":"Inspect","visible_events":[], '
            '"permitted_tools":[],"budget":{"steps":NaN}}'
        )
        with self.assertRaisesRegex(ValueError, "non-finite JSON constant"):
            AgentObservation.from_json(nonfinite)


class TestRecoveryRequestDigest(unittest.TestCase):
    def test_public_progress_trace_records_only_request_hashes(self) -> None:
        before = "public-state-token-private-canary-1"
        after = "public-state-token-private-canary-2"
        episode = RecoveryEpisode("request-5")
        self.assertTrue(episode.request_recovery(RecoveryAction.REFRESH, before_token=before))
        self.assertEqual(episode.trace[0]["before_token_digest"],
                         hashlib.sha256(before.encode("utf-8")).hexdigest())
        self.assertTrue(episode.resolve_recovery(RecoveryAction.REFRESH, after_token=after))
        serialized_trace = json.dumps(episode.trace, sort_keys=True)
        self.assertNotIn(before, serialized_trace)
        self.assertNotIn(after, serialized_trace)
        self.assertEqual(len(episode.trace[1]["after_token_digest"]), 64)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

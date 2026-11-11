"""Versioned request, digest, and recovery-trace compatibility contracts."""

from __future__ import annotations

import hashlib
import json
import math
import unittest

from memory_fabric import MemoryFabric
from memory_fabric.agent_outcomes import (
    AgentObservation, AgentStep, RECOVERY_ACTIONS, RecoveryAction, RecoveryCause,
    RecoveryEpisode, RecoveryFailureClass, RecoveryFeatureFlag, RecoveryLimits,
    RecoveryNextAction, RecoveryResolution, RecoveryStatus,
)
from memory_fabric.service import MemoryService


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


class TestRecoveryBudgets(unittest.TestCase):
    @staticmethod
    def _oscillating_audit() -> str:
        episode = RecoveryEpisode("audit-task", RecoveryLimits(max_steps=8,
                                                                  max_recoveries=3))
        episode.request_recovery(RecoveryAction.RE_RETRIEVE, before_token="state-A")
        episode.resolve_recovery(RecoveryAction.RE_RETRIEVE, after_token="state-B")
        episode.request_recovery(RecoveryAction.REPLAN, before_token="state-B")
        episode.resolve_recovery(RecoveryAction.REPLAN, after_token="state-A")
        return episode.canonical_audit_json()

    def test_budget_audit_is_deterministic_and_records_no_progress_failure(self) -> None:
        first = self._oscillating_audit()
        second = self._oscillating_audit()
        self.assertEqual(first, second)
        audit = json.loads(first)
        self.assertEqual(audit["schema_id"], "memory-fabric.recovery-audit.v3")
        self.assertEqual(audit["status"], "FAILED")
        self.assertEqual(audit["failure_reason"], "no_monotonic_progress")
        self.assertEqual(audit["budget"], {
            "max_steps": 8, "max_recoveries": 3, "max_event_bytes": 16_000,
            "deadline_s": 30.0,
        })
        self.assertEqual(audit["used"], {"steps": 4, "recoveries": 2})
        self.assertEqual(audit["telemetry"]["recovery_actions"]["re_retrieve"], 1)
        self.assertEqual(audit["telemetry"]["recovery_actions"]["replan"], 1)


class TestRecoveryGuidance(unittest.TestCase):
    def test_retrieval_failure_is_counted_and_uses_one_bounded_retry(self) -> None:
        episode = RecoveryEpisode("retrieval-telemetry")
        episode.record("evidence_blocked")

        guidance = episode.handle_failure(RecoveryCause.MISSING)
        self.assertEqual(guidance.next_action, RecoveryNextAction.RE_RETRIEVE)
        self.assertTrue(episode.request_recovery(
            RecoveryAction.RE_RETRIEVE, before_token="empty-result"))

        telemetry = episode.audit_record()["telemetry"]
        self.assertEqual(
            telemetry["failure_classes"][RecoveryFailureClass.RETRIEVAL.value], 1)
        self.assertEqual(
            telemetry["failure_classes"][RecoveryFailureClass.AUTHORIZATION.value], 0)
        self.assertEqual(telemetry["recovery_actions"][RecoveryAction.RE_RETRIEVE.value], 1)
        self.assertEqual(telemetry["requeries_avoided"], 0)
        self.assertTrue(episode.resolve_recovery(
            RecoveryAction.RE_RETRIEVE, after_token="one-result-returned"))
        self.assertEqual(
            episode.handle_failure(RecoveryCause.STALE).next_action,
            RecoveryNextAction.REFRESH,
        )
        repeated_telemetry = episode.audit_record()["telemetry"]
        self.assertEqual(
            repeated_telemetry["failure_classes"][RecoveryFailureClass.RETRIEVAL.value], 1)
        self.assertEqual(
            repeated_telemetry["failure_classes"][
                RecoveryFailureClass.EVIDENCE_VALIDITY.value], 1)

    def test_authorization_failure_blocks_and_counts_pointless_retrieval(self) -> None:
        episode = RecoveryEpisode("authorization-telemetry")
        episode.record("evidence_blocked")
        episode.handle_failure(RecoveryCause.UNAUTHORIZED)

        self.assertFalse(episode.request_recovery(
            RecoveryAction.RE_RETRIEVE, before_token="revoked-source"))
        telemetry = episode.audit_record()["telemetry"]
        self.assertEqual(
            telemetry["failure_classes"][RecoveryFailureClass.AUTHORIZATION.value], 1)
        self.assertEqual(
            telemetry["failure_classes"][RecoveryFailureClass.RETRIEVAL.value], 0)
        self.assertEqual(telemetry["recovery_actions"][RecoveryAction.RE_RETRIEVE.value], 0)
        self.assertEqual(telemetry["requeries_avoided"], 1)

    def test_fallback_is_structured_and_selects_only_a_read_only_action(self) -> None:
        episode = RecoveryEpisode("fallback-guidance")
        self.assertTrue(episode.record("evidence_blocked", {"reason": "stale"}))

        guidance = episode.handle_failure(RecoveryCause.STALE)

        self.assertEqual(guidance.resolution, RecoveryResolution.FALLBACK)
        self.assertEqual(guidance.next_action, RecoveryNextAction.REFRESH)
        action = RecoveryAction(guidance.next_action.value)
        self.assertTrue(RECOVERY_ACTIONS[action].read_only)
        self.assertEqual(episode.status, RecoveryStatus.BLOCKED)
        self.assertEqual(episode.audit_record()["guidance"], guidance.to_json())
        self.assertTrue(episode.request_recovery(action, before_token="old-evidence"))
        self.assertTrue(episode.resolve_recovery(action, after_token="current-evidence"))

    def test_authorization_failure_escalates_without_changing_grants(self) -> None:
        for cause in (RecoveryCause.UNAUTHORIZED, RecoveryCause.ERASED,
                      RecoveryCause.NO_INDEPENDENT_SOURCE):
            with self.subTest(cause=cause):
                episode = RecoveryEpisode(f"owner-escalation-{cause.value}")
                self.assertTrue(episode.record("evidence_blocked", {"reason": cause.value}))

                guidance = episode.handle_failure(cause)

                self.assertEqual(guidance.resolution, RecoveryResolution.ESCALATE)
                self.assertEqual(guidance.next_action,
                                 RecoveryNextAction.REQUEST_OWNER_REVIEW)
                self.assertTrue(guidance.requires_human)
                self.assertEqual(episode.status, RecoveryStatus.ESCALATED)
                self.assertFalse(episode.request_recovery(
                    RecoveryAction.REFRESH, before_token="try-to-override"))
                self.assertEqual(episode.audit_record()["guidance"]["cause"], cause.value)

    def test_unknown_failure_abstains_and_no_progress_escalates(self) -> None:
        unknown = RecoveryEpisode("unknown-stop")
        guidance = unknown.handle_failure(RecoveryCause.UNKNOWN)
        self.assertEqual(guidance.resolution, RecoveryResolution.ABSTAIN)
        self.assertEqual(guidance.next_action, RecoveryNextAction.ABSTAIN)
        self.assertEqual(unknown.status, RecoveryStatus.ABSTAINED)

        stalled = RecoveryEpisode("stalled-escalation", RecoveryLimits(max_recoveries=2))
        stalled.request_recovery(RecoveryAction.RE_RETRIEVE, before_token="state-A")
        self.assertFalse(stalled.resolve_recovery(
            RecoveryAction.RE_RETRIEVE, after_token="state-A"))
        progress_guidance = stalled.handle_failure(RecoveryCause.NO_MONOTONIC_PROGRESS)
        self.assertEqual(progress_guidance.resolution, RecoveryResolution.ESCALATE)
        self.assertEqual(stalled.status, RecoveryStatus.ESCALATED)
        self.assertEqual(stalled.audit_record()["failure_reason"], "no_monotonic_progress")


class TestRecoveryFeatureFlag(unittest.TestCase):
    def test_recovery_is_disabled_by_default_and_legacy_session_reads_still_work(self) -> None:
        service = MemoryService(MemoryFabric(":memory:", auto_activate=True))
        self.addCleanup(service.close)
        for agent in ("writer", "reader"):
            service.register_agent(agent, key=(agent * 8).encode("utf-8"),
                                   tenant_id="tenant-flag")
        writer = service.session(service.issue("writer"))
        reader = service.session(service.issue("reader"))
        memory_id = writer.remember("Pump pressure is currently four bar.", scope="team")
        feature = RecoveryFeatureFlag()

        self.assertFalse(feature.enabled)
        self.assertIsNone(feature.start_episode("legacy-task"))
        self.assertEqual([memory.id for memory in reader.retrieve("pump pressure").exposed],
                         [memory_id])

    def test_explicit_enablement_and_rollback_are_isolated_per_factory(self) -> None:
        enabled = RecoveryFeatureFlag(enabled=True, limits=RecoveryLimits(max_steps=4))
        episode = enabled.start_episode("opt-in-task")
        self.assertIsNotNone(episode)
        self.assertEqual(episode.limits.max_steps, 4)
        self.assertEqual(episode.status, RecoveryStatus.READY)

        disabled = RecoveryFeatureFlag()
        self.assertIsNone(disabled.start_episode("after-rollback"))
        self.assertEqual(episode.status, RecoveryStatus.READY)
        with self.assertRaises(ValueError):
            RecoveryFeatureFlag(enabled=1)

    def test_recovery_limits_and_step_exhaustion_fail_closed(self) -> None:
        for limits in (
            {"max_steps": True},
            {"max_steps": 1025},
            {"max_recoveries": 129},
            {"max_event_bytes": 64_001},
            {"deadline_s": math.nan},
            {"deadline_s": True},
            {"deadline_s": 3601.0},
        ):
            with self.subTest(limits=limits), self.assertRaises(ValueError):
                RecoveryLimits(**limits)

        episode = RecoveryEpisode("zero-budget", RecoveryLimits(max_steps=0))
        self.assertFalse(episode.record("inspect"))
        self.assertEqual(episode.failure_reason, "step_budget_exhausted")
        audit = episode.audit_record()
        self.assertEqual(audit["budget"]["max_steps"], 0)
        self.assertEqual(audit["used"]["steps"], 0)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

"""Versioned request, digest, and recovery-trace compatibility contracts."""

from __future__ import annotations

import hashlib
import json
import math
import unittest
from tempfile import TemporaryDirectory

from memory_fabric import MemoryFabric
from memory_fabric import certificates as certificate_codes
from memory_fabric.actions_typed import (
    ALREADY_EXECUTED, REFUSED, UNCERTAIN, ActionGate, ActionPolicy, ActionRequest, ToolRule,
)
from memory_fabric.outcome_typed import (
    AgentObservation, AgentStep, RECOVERY_ACTIONS, RecoveryAction, RecoveryCause,
    RecoveryEpisode, RecoveryFailureClass, RecoveryFeatureFlag, RecoveryLimits,
    RecoveryNextAction, RecoveryResolution, RecoveryStatus,
)
from memory_fabric.justification import JustificationKind, justification_context
from memory_fabric.service import MemoryService


class TestVersionedOutcomeRequests(unittest.TestCase):
    def test_correction_preserves_action_supported_by_an_independent_alternative(self) -> None:
        fabric = MemoryFabric(":memory:", auto_activate=True)
        self.addCleanup(fabric.close)
        corrected_root = fabric.remember(
            "source-a", "Pump beta independent reading is 6.", scope="team")
        surviving_root = fabric.remember(
            "source-b", "Separate probe confirms pump beta value is 6.", scope="team")
        conclusion = fabric.derive(
            "planner", "Pump beta target is 6.",
            parents=[corrected_root, surviving_root],
            context=justification_context((
                (corrected_root, JustificationKind.ALTERNATIVE),
                (surviving_root, JustificationKind.ALTERNATIVE),
            )), scope="team",
        )
        fabric.validate(conclusion, actor="supervisor")
        certificate = fabric.certify(
            "Set pump beta target to 6.", [conclusion], "executor",
            required_checks=[certificate_codes.CHECK_DEPENDENCIES_CURRENT],
        )

        fabric.quarantine(
            corrected_root, "source measurement corrected", actor="reviewer",
            basis="contradicted",
        )
        verification = fabric.verify_certificate(certificate, "executor")
        self.assertTrue(verification.ok, verification)
        self.assertTrue(any("support_survived" in note for note in verification.notes))

        request = ActionRequest("pump_beta", {"value": 6})
        gate = ActionGate(fabric, ActionPolicy(
            tools={"set_target": ToolRule("set_target", protected=False)},
            grants={"executor": frozenset({"set_target"})},
        ))
        effects: list[int] = []
        execution = gate.execute(
            "set_target", "executor", lambda _key: effects.append(6),
            certificate, key="alternative-survives-correction", request=request,
        )
        self.assertEqual(execution.outcome, "executed")
        self.assertEqual(effects, [6])

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
        with self.assertRaisesRegex(ValueError, "typed methods"):
            episode.record("recovery_requested")
        with self.assertRaisesRegex(ValueError, "typed methods"):
            episode.record("action_gate")
        self.assertTrue(episode.request_recovery(RecoveryAction.REFRESH, before_token=before))
        self.assertEqual(episode.trace[0]["before_token_digest"],
                         hashlib.sha256(before.encode("utf-8")).hexdigest())
        checkpoint = episode.canonical_checkpoint_json()
        self.assertNotIn(before, checkpoint)
        resumed = RecoveryEpisode.from_checkpoint(checkpoint, downtime_s=0)
        self.assertEqual(resumed.checkpoint_record()["pending_action"], "refresh")
        self.assertTrue(resumed.resolve_recovery(RecoveryAction.REFRESH, after_token=after))
        later = RecoveryEpisode.from_checkpoint(
            resumed.canonical_checkpoint_json(), downtime_s=0)
        self.assertTrue(later.request_recovery(
            RecoveryAction.REPLAN, before_token="public-state-token-private-canary-3"))
        self.assertFalse(later.resolve_recovery(
            RecoveryAction.REPLAN, after_token=after))
        serialized_trace = json.dumps(later.trace, sort_keys=True)
        self.assertNotIn(before, serialized_trace)
        self.assertNotIn(after, serialized_trace)
        self.assertEqual(len(later.trace[1]["after_token_digest"]), 64)
        invalid_checkpoint = episode.checkpoint_record()
        invalid_checkpoint["pending_action"] = None
        with self.assertRaisesRegex(ValueError, "pending action disagrees"):
            RecoveryEpisode.from_checkpoint(invalid_checkpoint, downtime_s=0)
        extra_audit_field = episode.checkpoint_record()
        extra_audit_field["audit"]["host_claim"] = "complete"
        with self.assertRaisesRegex(ValueError, "invalid audit record"):
            RecoveryEpisode.from_checkpoint(extra_audit_field, downtime_s=0)
        forged_receipt = episode.checkpoint_record()
        forged_receipt["audit"]["trace"].append({
            "kind": "action_gate",
            "detail": {"outcome": "executed", "reason_codes": []},
        })
        forged_receipt["audit"]["used"]["steps"] += 1
        forged_receipt["audit"]["status"] = RecoveryStatus.COMPLETE.value
        with self.assertRaisesRegex(ValueError, "unproposed ActionGate result"):
            RecoveryEpisode.from_checkpoint(forged_receipt, downtime_s=0)
        expired = RecoveryEpisode.from_checkpoint(checkpoint, downtime_s=31)
        self.assertEqual(expired.failure_reason, "deadline_exceeded")


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

    def test_checkpoint_restart_reconciles_action_without_rerunning_effect(self) -> None:
        with TemporaryDirectory() as folder:
            db_path = f"{folder}/store.db"
            fabric = MemoryFabric(db_path, auto_activate=True)
            evidence_id = fabric.remember(
                "sensor", "Target reading is 7 units.", scope="team")
            certificate = fabric.certify(
                "Set target to 7 units.", [evidence_id], "executor")
            request = ActionRequest("target", {"value": 7})
            policy = ActionPolicy(
                tools={"set_target": ToolRule("set_target", requires_grant=True)},
                grants={"executor": frozenset({"set_target"})},
            )
            gate = ActionGate(fabric, policy)
            grant = gate.issue_grant(
                "set_target", "executor", issuer="host",
                certificate=certificate, request=request,
            )
            episode = RecoveryEpisode("restartable-task")
            checkpoint = episode.canonical_checkpoint_json()
            forged_complete = json.loads(checkpoint)
            forged_complete["audit"]["status"] = RecoveryStatus.COMPLETE.value
            with self.assertRaisesRegex(ValueError, "no executed action receipt"):
                RecoveryEpisode.from_checkpoint(forged_complete, downtime_s=0)
            callback_calls: list[str] = []
            effects: set[str] = set()

            def effect(key: str) -> None:
                callback_calls.append(key)
                effects.add(key)

            try:
                first = episode.execute(
                    gate, "set_target", "executor", certificate, effect,
                    key="restartable-action-key", request=request, grant=grant,
                )
                self.assertEqual(first.outcome, "executed")
                self.assertEqual(episode.status, RecoveryStatus.COMPLETE)
                fabric.close()

                resumed = RecoveryEpisode.from_checkpoint(checkpoint, downtime_s=0)
                reopened = MemoryFabric(db_path)
                try:
                    repeated = resumed.execute(
                        ActionGate(reopened, policy), "set_target", "executor", certificate,
                        effect, key="restartable-action-key", request=request, grant=grant,
                    )
                    self.assertEqual(repeated.outcome, ALREADY_EXECUTED)
                    self.assertEqual(resumed.status, RecoveryStatus.COMPLETE)
                    self.assertEqual(callback_calls, ["restartable-action-key"])
                    self.assertEqual(effects, {"restartable-action-key"})
                finally:
                    reopened.close()
            finally:
                fabric.close()

    def test_checkpoint_restart_requires_explicit_retry_for_uncertain_effect(self) -> None:
        with TemporaryDirectory() as folder:
            db_path = f"{folder}/uncertain.db"
            fabric = MemoryFabric(db_path, auto_activate=True)
            evidence_id = fabric.remember(
                "sensor", "Target reading is 8 units.", scope="team")
            certificate = fabric.certify(
                "Set target to 8 units.", [evidence_id], "executor")
            request = ActionRequest("target", {"value": 8})
            policy = ActionPolicy(
                tools={"set_target": ToolRule("set_target", requires_grant=True)},
                grants={"executor": frozenset({"set_target"})},
            )
            gate = ActionGate(fabric, policy)
            grant = gate.issue_grant(
                "set_target", "executor", issuer="host",
                certificate=certificate, request=request,
            )
            episode = RecoveryEpisode("uncertain-restart-task")
            calls: list[str] = []
            effects: set[str] = set()

            def effect(key: str) -> None:
                calls.append(key)
                if key not in effects:
                    effects.add(key)
                    raise RuntimeError("effect committed; response was lost")

            try:
                first = episode.execute(
                    gate, "set_target", "executor", certificate, effect,
                    key="uncertain-action-key", request=request, grant=grant,
                )
                self.assertEqual(first.outcome, UNCERTAIN)
                self.assertEqual(episode.status, RecoveryStatus.BLOCKED)
                checkpoint = episode.canonical_checkpoint_json()
                fabric.close()

                resumed = RecoveryEpisode.from_checkpoint(checkpoint, downtime_s=0)
                reopened = MemoryFabric(db_path)
                try:
                    gate_after_restart = ActionGate(reopened, policy)
                    refused = resumed.execute(
                        gate_after_restart, "set_target", "executor", certificate,
                        effect, key="uncertain-action-key", request=request, grant=grant,
                    )
                    self.assertEqual(refused.outcome, REFUSED)
                    self.assertEqual(calls, ["uncertain-action-key"])
                    retry_grant = gate_after_restart.issue_grant(
                        "set_target", "executor", issuer="host-retry",
                        certificate=certificate, request=request,
                    )
                    retried = resumed.execute(
                        gate_after_restart, "set_target", "executor", certificate,
                        effect, key="uncertain-action-key", request=request,
                        grant=retry_grant, retry=True,
                    )
                    self.assertEqual(retried.outcome, "executed")
                    self.assertEqual(resumed.status, RecoveryStatus.COMPLETE)
                    self.assertEqual(calls, ["uncertain-action-key", "uncertain-action-key"])
                    self.assertEqual(effects, {"uncertain-action-key"})
                finally:
                    reopened.close()
            finally:
                fabric.close()


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

"""Contract coverage for truth-free experimental agent outcomes."""

from __future__ import annotations

import hashlib
import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from benchmarks.outcome_report import (
    canonical_report, paired_completion_analysis, zero_event_upper_bound,
)
from benchmarks.outcome_recovery import main, run_episode, run_paired, visible_observation
from examples.outcome_recovery_demo import run_demo
from memory_fabric.agent_outcomes import (
    AgentObservation, AgentStep, DiagnosisSource, EpisodeOutcome, EvidenceFailureCode,
    FailureCode, RECOVERY_ACTIONS, RecoveryAction, RecoveryEpisode, RecoveryLimits,
    RecoveryStatus, diagnose_access, diagnose_answerability, diagnose_certificate,
    diagnose_relevance,
)
from memory_fabric.answerability import Answerability
from memory_fabric.certificates import CertificateVerification
from memory_fabric.enforcement import AccessDecision, RiskLevel, Verdict
from memory_fabric.relevance import ReasonCode


class TestOutcomeContracts(unittest.TestCase):
    def test_evidence_diagnosis_classifies_access_without_leaking_details(self) -> None:
        denied = AccessDecision("private-memory", 0, Verdict.DENY, "not_visible",
                                detail="secret memory contents")
        diagnosis = diagnose_access(denied)
        self.assertEqual(diagnosis.source, DiagnosisSource.ACCESS)
        self.assertEqual(diagnosis.failure_codes, (EvidenceFailureCode.UNAUTHORIZED,))
        self.assertEqual(diagnosis.suggested_actions, ())
        serialized = json.dumps(diagnosis.to_json())
        self.assertNotIn("private-memory", serialized)
        self.assertNotIn("secret memory contents", serialized)

        expected = {
            "not_found": EvidenceFailureCode.MISSING,
            "candidate_unvalidated": EvidenceFailureCode.WITHHELD,
            "contested": EvidenceFailureCode.CONTESTED,
            "version_moved": EvidenceFailureCode.STALE,
            "made_up_code": EvidenceFailureCode.UNKNOWN,
        }
        for reason, failure in expected.items():
            with self.subTest(reason=reason):
                row = AccessDecision("opaque", 1, Verdict.DENY, reason,
                                     risk=RiskLevel.HIGH)
                self.assertEqual(diagnose_access(row).failure_codes, (failure,))

        deleted = AccessDecision("opaque", 1, Verdict.DENY, "blocked_lifecycle",
                                 lifecycle_state="deleted")
        self.assertEqual(diagnose_access(deleted).failure_codes,
                         (EvidenceFailureCode.ERASED,))
        active = AccessDecision("opaque", 1, Verdict.USABLE, "active")
        self.assertEqual(diagnose_access(active).failure_codes, ())

    def test_evidence_diagnosis_maps_certificates_and_unknown_reasons_fail_closed(self) -> None:
        verified = CertificateVerification(True, ("ok",), {})
        self.assertEqual(diagnose_certificate(verified).failure_codes, ())

        refused = CertificateVerification(
            False, ("evidence_version_moved", "future_reason"), {},
            notes=("private text must not be copied",),
        )
        diagnosis = diagnose_certificate(refused)
        self.assertEqual(diagnosis.failure_codes,
                         (EvidenceFailureCode.STALE, EvidenceFailureCode.UNKNOWN))
        self.assertEqual(diagnosis.suggested_actions,
                         (RecoveryAction.REFRESH, RecoveryAction.RE_RETRIEVE))
        self.assertNotIn("private text", json.dumps(diagnosis.to_json()))

        unauthorized = CertificateVerification(False, ("wrong_tenant",), {})
        self.assertEqual(diagnose_certificate(unauthorized).failure_codes,
                         (EvidenceFailureCode.UNAUTHORIZED,))
        empty = CertificateVerification(False, (), {})
        self.assertEqual(diagnose_certificate(empty).failure_codes,
                         (EvidenceFailureCode.UNKNOWN,))

    def test_evidence_diagnosis_uses_answerability_verdict_and_exposure_count(self) -> None:
        insufficient = Answerability("insufficient", reasons=("private claim text",))
        retrieved_but_irrelevant = diagnose_answerability(insufficient, exposed_count=2)
        self.assertEqual(retrieved_but_irrelevant.failure_codes,
                         (EvidenceFailureCode.IRRELEVANT,))
        self.assertNotIn("private claim text", json.dumps(retrieved_but_irrelevant.to_json()))
        no_exposure = diagnose_answerability(insufficient, exposed_count=0)
        self.assertEqual(no_exposure.failure_codes, (EvidenceFailureCode.INSUFFICIENT,))
        contested = diagnose_answerability(Answerability("conflicting"), exposed_count=2)
        self.assertEqual(contested.failure_codes, (EvidenceFailureCode.CONTESTED,))
        unknown = diagnose_answerability(Answerability("future_verdict"), exposed_count=0)
        self.assertEqual(unknown.failure_codes, (EvidenceFailureCode.UNKNOWN,))
        with self.assertRaisesRegex(ValueError, "cannot be negative"):
            diagnose_answerability(insufficient, exposed_count=-1)

    def test_evidence_diagnosis_classifies_duplicate_relevance_and_unknown_input(self) -> None:
        duplicate = diagnose_relevance(ReasonCode.DUPLICATE_OR_REDUNDANT)
        self.assertEqual(duplicate.failure_codes, (EvidenceFailureCode.DUPLICATE,))
        unknown = diagnose_relevance("not_a_reason_code")
        self.assertEqual(unknown.failure_codes, (EvidenceFailureCode.UNKNOWN,))
        self.assertEqual(unknown.suggested_actions, ())

    def test_observation_canonical_roundtrip_and_digest(self) -> None:
        observation = AgentObservation("task-1", "Check the current reading.",
                                       ({"source": "sensor", "value": "normal"},),
                                       ("retrieve", "inspect"), {"steps": 4})
        restored = AgentObservation.from_json(observation.canonical_json())
        self.assertEqual(restored, observation)
        self.assertEqual(restored.schema_id, "memory-fabric.agent-outcomes.v3")
        self.assertEqual(restored.request_digest(), observation.request_digest())
        self.assertEqual(len(observation.request_digest()), 64)

    def test_observation_rejects_oracle_fields_recursively(self) -> None:
        for field in ("truth", "expected_action", "evidence_usable", "reward"):
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, "evaluator-only"):
                    AgentObservation("task-1", "Do task", ({"metadata": {field: True}},), (), {})

    def test_contracts_reject_unknown_fields_and_unbounded_payloads(self) -> None:
        with self.assertRaisesRegex(ValueError, "fields do not match"):
            AgentObservation.from_json('{"schema_id":"memory-fabric.agent-outcomes.v3",'
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
                              hashlib.sha256(b"sealed outcome").hexdigest(),
                              terminal_failure_codes=(FailureCode.STALE_DATA.value,
                                                      FailureCode.RETRIEVAL_MISS.value))
        report = canonical_report([good])
        self.assertIn('"population":"SCRIPTED_AGENT"', report)
        self.assertIn('"schema_id":"memory-fabric.outcome-report.v3"', report)
        self.assertIn('"terminal_failure_codes":["stale_data","retrieval_miss"]', report)
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            EpisodeOutcome("task-1", "A5", 1, True, 0, 0, 0, 0, 0, 0, 0, 1.0, "truth")
        with self.assertRaisesRegex(ValueError, "cannot exceed attempted"):
            EpisodeOutcome("task-1", "A5", 1, True, 1, 0, 0, 1, 0, 0, 0, 1.0,
                           hashlib.sha256(b"case").hexdigest(),
                           attempted_unsafe_effects=0, executed_unsafe_effects=1)
        with self.assertRaisesRegex(ValueError, "require at least one"):
            EpisodeOutcome("task-1", "A5", 1, False, 0, 0, 0, 0, 0, 0, 0, 1.0,
                           hashlib.sha256(b"case").hexdigest())
        with self.assertRaisesRegex(ValueError, "unsupported terminal failure"):
            EpisodeOutcome("task-1", "A5", 1, False, 0, 0, 0, 0, 0, 0, 0, 1.0,
                           hashlib.sha256(b"case").hexdigest(),
                           terminal_failure_codes=("made_up_failure",))

    def test_recovery_episode_is_bounded_and_terminal(self) -> None:
        episode = RecoveryEpisode("task-1")
        self.assertTrue(episode.record("evidence_blocked", {"reason": "stale"}))
        self.assertIs(episode.status, RecoveryStatus.BLOCKED)
        self.assertTrue(episode.request_recovery(RecoveryAction.REPLAN,
                                                 before_token="state-0"))
        self.assertTrue(episode.resolve_recovery(RecoveryAction.REPLAN,
                                                 after_token="state-1"))
        self.assertEqual(episode.recoveries, 1)
        self.assertTrue(episode.record("abstain"))
        self.assertIs(episode.status, RecoveryStatus.ABSTAINED)
        self.assertFalse(episode.record("replan"))
        with self.assertRaisesRegex(ValueError, "request_recovery"):
            RecoveryEpisode("task-2").record("replan")

    def test_recovery_catalog_is_read_only_and_rejects_no_progress_cycles(self) -> None:
        self.assertTrue(RECOVERY_ACTIONS)
        self.assertTrue(all(spec.read_only for spec in RECOVERY_ACTIONS.values()))
        with self.assertRaises(ValueError):
            RecoveryAction("set_target")

        episode = RecoveryEpisode("task-1", RecoveryLimits(max_recoveries=3))
        self.assertTrue(episode.request_recovery(RecoveryAction.RE_RETRIEVE,
                                                 before_token="state-A"))
        self.assertTrue(episode.resolve_recovery(RecoveryAction.RE_RETRIEVE,
                                                 after_token="state-B"))
        self.assertTrue(episode.request_recovery(RecoveryAction.REPLAN,
                                                 before_token="state-B"))
        self.assertFalse(episode.resolve_recovery(RecoveryAction.REPLAN,
                                                  after_token="state-A"))
        self.assertIs(episode.status, RecoveryStatus.FAILED)

    def test_recovery_deadline_fails_closed(self) -> None:
        with patch("memory_fabric.agent_outcomes.recovery.time.monotonic",
                   side_effect=[10.0, 12.0]):
            episode = RecoveryEpisode("task-1", RecoveryLimits(deadline_s=1.0))
            self.assertFalse(episode.record("inspect"))
            self.assertIs(episode.status, RecoveryStatus.FAILED)

    def test_zero_event_bound_is_not_zero_risk(self) -> None:
        bound = zero_event_upper_bound(0, 20)
        self.assertAlmostEqual(bound, 0.139108, delta=1e-6)
        self.assertAlmostEqual(zero_event_upper_bound(1, 20), 0.216106, delta=1e-6)

    def test_paired_analysis_is_clustered_deterministic_and_checks_negative_control(self) -> None:
        digest = hashlib.sha256(b"sealed case").hexdigest()

        def row(task: str, arm: str, seed: int, complete: bool) -> EpisodeOutcome:
            return EpisodeOutcome(
                task, arm, seed, complete, 0, 0, 0, 0, 0, 0, 0, 1.0, digest,
                terminal_failure_codes=() if complete else ("planning_error",),
            )

        outcomes = []
        base = (False, False, True, True, False)
        candidate = (True, True, True, True, False)
        for seed, (base_result, candidate_result) in enumerate(zip(base, candidate)):
            task = f"case-{seed}"
            outcomes.extend((row(task, "A0", seed, base_result),
                             row(task, "A5", seed, candidate_result)))
        analysis = paired_completion_analysis(outcomes, "A0", "A5", seed=7,
                                              resamples=500)
        self.assertEqual(analysis["mean_paired_difference"], 0.4)
        self.assertEqual(analysis["n_independent_clusters"], 5)
        self.assertEqual(analysis["pair_counts"],
                         {"treatment_wins": 2, "baseline_wins": 0, "ties": 3})
        self.assertEqual(analysis["cluster_exact_sign_test_p"], 0.5)
        self.assertTrue(analysis["minimum_cluster_floor_met"])
        self.assertEqual(analysis, paired_completion_analysis(
            outcomes, "A0", "A5", seed=7, resamples=500))

        negative_control = paired_completion_analysis(outcomes, "A0", "A0", seed=7,
                                                      resamples=500)
        self.assertTrue(negative_control["negative_control"])
        self.assertTrue(negative_control["minimum_cluster_floor_met"])
        self.assertEqual(negative_control["mean_paired_difference"], 0.0)
        self.assertEqual(negative_control["cluster_exact_sign_test_p"], 1.0)

    def test_scripted_recovery_uses_gate_and_paired_abstention(self) -> None:
        recovered = run_episode(0)
        abstained = run_episode(0, arm="A0")
        self.assertTrue(recovered.completion)
        self.assertEqual(recovered.successful_recoveries, 1)
        self.assertEqual(recovered.rejected_effects, 1)
        self.assertEqual(recovered.attempted_unsafe_effects, 1)
        self.assertEqual(recovered.executed_unsafe_effects, 0)
        self.assertEqual(recovered.safety_violations, 0)
        self.assertFalse(abstained.completion)
        self.assertEqual(abstained.successful_recoveries, 0)
        self.assertEqual(abstained.attempted_unsafe_effects, 0)
        self.assertEqual(abstained.terminal_failure_codes, ("abstention_cost",))
        self.assertEqual(abstained.outcome_oracle_digest, recovered.outcome_oracle_digest)

    def test_no_correction_uses_current_evidence_without_oracle_access(self) -> None:
        outcome = run_episode(1)
        self.assertTrue(outcome.completion)
        self.assertEqual(outcome.eligible_recoveries, 0)
        self.assertEqual(outcome.successful_recoveries, 0)
        observation = visible_observation(1)
        self.assertNotIn("truth", observation.canonical_json())
        self.assertFalse(any(event.get("status") == "correction"
                             for event in observation.visible_events))
        rows = run_paired((0, 1))
        self.assertEqual([(row.seed, row.arm) for row in rows],
                         [(0, "A0"), (0, "A5"), (1, "A0"), (1, "A5")])

    def test_paired_runner_rejects_duplicate_seeds_and_cli_emits_json(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-empty and unique"):
            run_paired((1, 1))
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(["--seeds", "1"]), 0)
        report = json.loads(output.getvalue())
        self.assertEqual(report["population"], "SCRIPTED_AGENT")
        self.assertEqual(len(report["rows"]), 2)
        self.assertTrue(all("executed_unsafe_effects" in row for row in report["rows"]))
        with self.assertRaisesRegex(ValueError, "arm must be"):
            run_episode(0, arm="invalid")

    def test_incident_demo_separates_actor_trace_from_evaluator(self) -> None:
        report = run_demo()
        actor = report["actor_view"]
        evaluator = report["evaluator_view_after_episode"]
        self.assertEqual([step["kind"] for step in actor], [
            "observation", "retrieve", "correction_received", "action_refused",
            "replan", "action_executed",
        ])
        self.assertTrue(all("completion" not in step for step in actor))
        self.assertTrue(evaluator["completion"])
        self.assertEqual(evaluator["unsafe_effects_executed"], 0)

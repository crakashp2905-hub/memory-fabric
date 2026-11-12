"""Counterfactual replay requires a complete, version-pinned host contract."""

from __future__ import annotations

import unittest

from memory_fabric.agent_outcomes import (
    OutcomeBenefitLabel, PolicyFlipLabel, ReplayContractStatus,
    ReplayFidelityLabel, build_authorized_replay_contract,
    dispatch_counterfactual_replay, label_counterfactual_evidence,
)
from memory_fabric import MemoryFabric
from memory_fabric.actions import REFUSED, ActionGate, ActionPolicy, ToolRule


def _complete_trace() -> dict[str, object]:
    return {
        "task_id": "task-1",
        "decision_id": "decision-1",
        "actor_id": "executor",
        "model_id": "local-model",
        "model_version": "checkpoint-7",
        "model_sha256": "a" * 64,
        "policy_id": "governed-policy",
        "policy_version": "policy-3",
        "policy_sha256": "b" * 64,
        "observation_sha256": "c" * 64,
        "decision_sha256": "d" * 64,
        "evidence_epochs": [["memory-a", 4], ["memory-b", 2]],
        "authorization_sha256": "e" * 64,
    }


class TestOutcomeCounterfactual(unittest.TestCase):
    def test_changed_proposal_is_not_reported_as_outcome_benefit_or_cause(self) -> None:
        report = label_counterfactual_evidence(
            replay_fidelity=ReplayFidelityLabel.EXACT,
            baseline_decision_sha256="a" * 64,
            alternative_decision_sha256="b" * 64,
            baseline_terminal_outcome=True,
            alternative_terminal_outcome=True,
        )

        self.assertEqual(report["replay_fidelity"], "EXACT")
        self.assertEqual(report["policy_flip"], PolicyFlipLabel.FLIPPED.value)
        self.assertEqual(report["outcome_benefit"], OutcomeBenefitLabel.NO_CHANGE.value)
        self.assertEqual(report["real_world_causality"], "NOT_ESTABLISHED")
        self.assertFalse(report["physical_root_cause_established"])

    def test_observed_paired_benefit_remains_distinct_from_physical_causality(self) -> None:
        report = label_counterfactual_evidence(
            replay_fidelity=ReplayFidelityLabel.DIVERGED,
            baseline_decision_sha256="a" * 64,
            alternative_decision_sha256="b" * 64,
            baseline_terminal_outcome=False,
            alternative_terminal_outcome=True,
        )

        self.assertEqual(report["outcome_benefit"], OutcomeBenefitLabel.IMPROVED.value)
        self.assertEqual(report["real_world_causality"], "NOT_ESTABLISHED")
        self.assertFalse(report["causal_effect_established"])

    def test_missing_decision_or_terminal_evidence_is_undecidable(self) -> None:
        report = label_counterfactual_evidence(
            replay_fidelity=ReplayFidelityLabel.UNVERIFIABLE,
            baseline_decision_sha256=None,
            alternative_decision_sha256="b" * 64,
            baseline_terminal_outcome=False,
            alternative_terminal_outcome=None,
        )

        self.assertEqual(report["policy_flip"], PolicyFlipLabel.UNDECIDABLE.value)
        self.assertEqual(report["outcome_benefit"], OutcomeBenefitLabel.UNDECIDABLE.value)

    def test_complete_trace_pins_model_policy_decision_and_evidence_epochs(self) -> None:
        built = build_authorized_replay_contract(_complete_trace())

        self.assertEqual(built.status, ReplayContractStatus.REPLAYABLE)
        self.assertEqual(built.reasons, ())
        self.assertIsNotNone(built.contract)
        assert built.contract is not None
        serialized = built.contract.to_dict()
        self.assertEqual(serialized["model_version"], "checkpoint-7")
        self.assertEqual(serialized["policy_version"], "policy-3")
        self.assertEqual(serialized["evidence_epochs"], [["memory-a", 4], ["memory-b", 2]])
        self.assertEqual(len(built.contract.contract_sha256), 64)

    def test_incomplete_trace_is_non_replayable_without_filling_missing_facts(self) -> None:
        trace = _complete_trace()
        del trace["model_version"]
        del trace["policy_sha256"]
        del trace["evidence_epochs"]

        built = build_authorized_replay_contract(trace)

        self.assertEqual(built.status, ReplayContractStatus.NON_REPLAYABLE)
        self.assertIsNone(built.contract)
        self.assertEqual(
            built.reasons,
            ("missing:evidence_epochs", "missing:model_version", "missing:policy_sha256"),
        )

    def test_unknown_trace_fields_and_malformed_epochs_fail_closed(self) -> None:
        hidden = _complete_trace()
        hidden["evaluator_truth"] = "forged"
        unknown = build_authorized_replay_contract(hidden)
        self.assertEqual(unknown.status, ReplayContractStatus.NON_REPLAYABLE)
        self.assertEqual(unknown.reasons, ("unknown:evaluator_truth",))

        malformed = _complete_trace()
        malformed["evidence_epochs"] = [["memory-a", True]]
        invalid = build_authorized_replay_contract(malformed)
        self.assertEqual(invalid.status, ReplayContractStatus.NON_REPLAYABLE)
        self.assertEqual(invalid.reasons, ("invalid:evidence_epochs",))

    def test_contract_digest_changes_when_any_pinned_input_changes(self) -> None:
        first = build_authorized_replay_contract(_complete_trace())
        changed_trace = _complete_trace()
        changed_trace["policy_version"] = "policy-4"
        changed = build_authorized_replay_contract(changed_trace)

        self.assertIsNotNone(first.contract)
        self.assertIsNotNone(changed.contract)
        assert first.contract is not None and changed.contract is not None
        self.assertNotEqual(first.contract.contract_sha256, changed.contract.contract_sha256)

    def test_replay_proposal_and_positive_result_do_not_authorize_an_effect(self) -> None:
        fabric = MemoryFabric(":memory:", auto_activate=True)
        self.addCleanup(fabric.close)
        replay = dispatch_counterfactual_replay(
            {"tool": "set_target", "value": 4},
            {"tool": "set_target", "value": 9},
            dependence_checked=True,
            depends_on_memory=True,
            worker_id="proposal_echo",
        )
        effects: list[str] = []
        gate = ActionGate(fabric, ActionPolicy(
            tools={"set_target": ToolRule("set_target")},
            grants={"executor": frozenset({"set_target"})},
        ))

        outcome = gate.execute(
            "set_target", "executor", effects.append, replay.result,
            key="replay-does-not-authorize",
        )

        self.assertEqual(replay.status.value, "INVOKED")
        self.assertEqual(outcome.outcome, REFUSED)
        self.assertEqual(effects, [])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

"""Counterfactual replay requires a complete, version-pinned host contract."""

from __future__ import annotations

import unittest

from memory_fabric.agent_outcomes import (
    ReplayContractStatus, build_authorized_replay_contract,
)


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


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

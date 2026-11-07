from __future__ import annotations

import threading
import unittest

from memory_fabric import MemoryFabric
from memory_fabric.actions import EXECUTED, REFUSED, ActionGate, ActionPolicy, ToolRule
from memory_fabric.events import EventType


def gate_for(fabric: MemoryFabric) -> ActionGate:
    return ActionGate(
        fabric,
        ActionPolicy(
            tools={"open": ToolRule("open")},
            grants={"ops": frozenset({"open"})},
        ),
    )


class DeterministicCorrectionRetrievalActionRaces(unittest.TestCase):
    def setUp(self) -> None:
        self.fabric = MemoryFabric(":memory:", auto_activate=True)
        self.addCleanup(self.fabric.close)
        self.mid = self.fabric.remember(
            "writer", "Valve V7 opens below 4 bar.", scope="team"
        )

    def test_fenced_action_commits_before_waiting_correction(self) -> None:
        certificate = self.fabric.certify("open-v7", [self.mid], "ops")
        tool_entered = threading.Event()
        allow_effect_to_finish = threading.Event()
        correction_attempted = threading.Event()
        correction_committed = threading.Event()
        action_done = threading.Event()
        results = []

        def tool(key: str) -> str:
            tool_entered.set()
            self.assertTrue(allow_effect_to_finish.wait(5), "test controller stalled")
            return key

        def run_action() -> None:
            results.append(
                gate_for(self.fabric).execute(
                    "open", "ops", tool, certificate, key="barrier-action", lease_s=3
                )
            )
            action_done.set()

        def correct() -> None:
            correction_attempted.set()
            self.fabric.revise(
                self.mid,
                "Valve V7 must remain closed.",
                agent_id="writer",
                reason="late inspection",
            )
            correction_committed.set()

        action = threading.Thread(target=run_action)
        action.start()
        self.assertTrue(tool_entered.wait(5))
        correction = threading.Thread(target=correct)
        correction.start()
        self.assertTrue(correction_attempted.wait(5))
        self.assertFalse(
            correction_committed.wait(0.2),
            "correction committed through the action transaction fence",
        )
        allow_effect_to_finish.set()
        self.assertTrue(action_done.wait(5))
        action.join(5)
        correction.join(5)
        self.assertTrue(correction_committed.is_set())
        self.assertEqual(results[0].outcome, EXECUTED)

        ordered = self.fabric.log.read_types(
            [EventType.ACTION_EXECUTED, EventType.MEMORY_VERSIONED]
        )
        executed = next(e.seq for e in ordered if e.type == EventType.ACTION_EXECUTED)
        corrected = next(e.seq for e in ordered if e.type == EventType.MEMORY_VERSIONED)
        self.assertLess(executed, corrected)

    def test_correction_after_retrieval_invalidates_later_action(self) -> None:
        retrieved = self.fabric.retrieve("ops", "Valve V7 opens below 4 bar", k=3)
        self.assertEqual([m.id for m in retrieved.exposed], [self.mid])
        certificate = self.fabric.certify("open-v7", [self.mid], "ops")
        allow_correction = threading.Event()
        correction_committed = threading.Event()

        def correct() -> None:
            self.assertTrue(allow_correction.wait(5))
            self.fabric.revise(
                self.mid,
                "Valve V7 must remain closed.",
                agent_id="writer",
                reason="late inspection",
            )
            correction_committed.set()

        worker = threading.Thread(target=correct)
        worker.start()
        allow_correction.set()
        self.assertTrue(correction_committed.wait(5))
        effects: list[str] = []
        result = gate_for(self.fabric).execute(
            "open", "ops", effects.append, certificate, key="stale-retrieval"
        )
        worker.join(5)
        self.assertEqual(result.outcome, REFUSED)
        self.assertEqual(effects, [])
        self.assertIsNotNone(result.decision)
        self.assertIn("evidence_version_moved", result.decision.reason_codes)
        receipts = self.fabric.log.read_types([EventType.ACTION_EXECUTED])
        self.assertEqual([event.payload["outcome"] for event in receipts], ["refused"])

    def test_prior_allowed_authorization_is_not_reused_after_correction(self) -> None:
        gate = gate_for(self.fabric)
        certificate = self.fabric.certify("open-v7", [self.mid], "ops")
        planned = gate.authorize("open", "ops", certificate)
        self.assertTrue(planned.allowed, "the pre-correction plan should initially qualify")

        self.fabric.revise(self.mid, "Valve V7 must remain closed.", agent_id="writer",
                           reason="inspection before execution")
        effects: list[str] = []
        result = gate.execute("open", "ops", effects.append, certificate,
                              key="authorize-then-execute-correction")

        self.assertEqual(result.outcome, REFUSED)
        self.assertEqual(effects, [], "execute must revalidate live evidence, not reuse plan approval")
        self.assertIsNotNone(result.decision)
        self.assertIn("evidence_version_moved", result.decision.reason_codes)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

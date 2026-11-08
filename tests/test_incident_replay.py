from __future__ import annotations

import copy
import json
import unittest

from memory_fabric import MemoryFabric
from memory_fabric.actions import ActionGate, ActionPolicy, ToolRule
from memory_fabric.events import EventType
from memory_fabric.observability.incident_export import (
    export_incident, replay_redacted_incident,
)


class RedactedIncidentReplay(unittest.TestCase):
    def _artifact(self):
        fabric = MemoryFabric(":memory:", auto_activate=True, seed=0)
        self.addCleanup(fabric.close)
        secret = "PRIVATE-CANARY-incident-payload"
        memory_id = fabric.remember("agent", f"Evidence contains {secret}", scope="team")
        gate = ActionGate(fabric, ActionPolicy(
            tools={"ship": ToolRule("ship")}, grants={"agent": frozenset({"ship"})}
        ))
        gate.authorize("ship", "agent", fabric.certify("shipment", [memory_id], "agent"))
        action = next(e for e in fabric.log.read_types([EventType.ACTION_GATED]))
        return fabric, action.seq, secret

    def test_same_history_replays_identically_from_redacted_artifact(self) -> None:
        fabric, action_seq, secret = self._artifact()
        first = export_incident(fabric, action_seq)
        second = export_incident(fabric, action_seq)
        self.assertEqual(first, second)
        self.assertNotIn(secret, json.dumps(first))
        # The replay consumes only the exported redacted object; no fabric/store
        # is passed and repeated output must be byte stable.
        replay_a = replay_redacted_incident(first)
        replay_b = replay_redacted_incident(json.loads(json.dumps(first)))
        self.assertEqual(replay_a, replay_b)
        self.assertEqual(replay_a["explanation"]["decision"], "allowed")

    def test_digest_mismatch_is_rejected_before_explanation(self) -> None:
        fabric, action_seq, _ = self._artifact()
        altered = copy.deepcopy(export_incident(fabric, action_seq))
        altered["report"]["tool"] = "forged"
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            replay_redacted_incident(altered)


if __name__ == "__main__":
    unittest.main()

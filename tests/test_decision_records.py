from __future__ import annotations

import json
import unittest

from memory_fabric import (
    DecisionEdge, DecisionEdgeError, DecisionLedger, DecisionOption, DecisionRecord,
    DecisionTransitionError, Event, EventLog, EventType, EvidenceVersion,
)


class DecisionRecordSchemaTests(unittest.TestCase):
    def make_record(self) -> DecisionRecord:
        evidence = EvidenceVersion("memory-17", 3)
        return DecisionRecord(
            decision_id="decision-42",
            tenant_id="tenant-1",
            agent_id="agent-7",
            decided_at="2026-11-08T10:00:00Z",
            goal="Choose a safe deployment window",
            options=(
                DecisionOption("morning", "Deploy in the morning", (evidence,)),
                DecisionOption("defer", "Defer deployment", ()),
            ),
            chosen_option_id="morning",
            evidence_versions=(evidence,),
            constraints={"max_downtime_minutes": 15, "change_freeze": False},
        )

    def test_v1_round_trip_preserves_goal_options_evidence_and_constraints(self) -> None:
        original = self.make_record()
        payload = json.loads(json.dumps(original.to_dict()))
        restored = DecisionRecord.from_dict(payload)
        self.assertEqual(restored, original)
        self.assertEqual(restored.to_dict(), payload)
        self.assertEqual(restored.options[0].evidence, (EvidenceVersion("memory-17", 3),))

    def test_record_and_nested_constraints_are_immutable(self) -> None:
        constraints = {"region": "eu-west"}
        record = DecisionRecord("d1", "tenant-1", "agent-1", "2026-11-08T10:00:00Z",
                                "goal", (DecisionOption("a", "Option A"),),
                                "a", (), constraints)
        constraints["region"] = "us-east"
        self.assertEqual(record.constraints["region"], "eu-west")
        with self.assertRaises(TypeError):
            record.constraints["region"] = "us-east"  # type: ignore[index]

    def test_rejects_duplicate_or_unknown_option_selection(self) -> None:
        with self.assertRaisesRegex(ValueError, "unique"):
            DecisionRecord("d1", "tenant-1", "agent-1", "2026-11-08T10:00:00Z",
                           "goal", (DecisionOption("a", "A"),
                                    DecisionOption("a", "duplicate")), "a", (), {})
        with self.assertRaisesRegex(ValueError, "registered option"):
            DecisionRecord("d1", "tenant-1", "agent-1", "2026-11-08T10:00:00Z",
                           "goal", (DecisionOption("a", "A"),), "missing", (), {})

    def test_rejects_invalid_evidence_versions_status_and_schema(self) -> None:
        with self.assertRaisesRegex(ValueError, "positive integer"):
            EvidenceVersion("m1", 0)
        with self.assertRaisesRegex(ValueError, "status"):
            DecisionRecord("d1", "tenant-1", "agent-1", "2026-11-08T10:00:00Z",
                           "goal", (DecisionOption("a", "A"),), None,
                           (), {}, status="complete")
        payload = self.make_record().to_dict()
        payload["unregistered"] = True
        with self.assertRaisesRegex(ValueError, "fields"):
            DecisionRecord.from_dict(payload)
        for required in ("decision_id", "tenant_id", "agent_id", "decided_at"):
            incomplete = self.make_record().to_dict()
            del incomplete[required]
            with self.assertRaisesRegex(ValueError, "fields"):
                DecisionRecord.from_dict(incomplete)
        with self.assertRaisesRegex(ValueError, "timezone offset"):
            DecisionRecord("d2", "tenant-1", "agent-1", "2026-11-08T10:00:00",
                           "goal", (DecisionOption("a", "A"),), None, (), {})

    def test_status_vocabulary_requires_a_selected_option_after_proposal(self) -> None:
        base = self.make_record()
        for status in ("proposed", "approved", "executed", "superseded",
                       "requires_reconsideration"):
            if status == "proposed":
                record = base
            else:
                record = base.transition_status("approved", changed_at="2026-11-08T10:01:00Z",
                                                actor_id="reviewer")
                if status == "executed":
                    record = record.transition_status("executed", changed_at="2026-11-08T10:02:00Z",
                                                       actor_id="operator")
                elif status in {"superseded", "requires_reconsideration"}:
                    record = record.transition_status(status, changed_at="2026-11-08T10:02:00Z",
                                                      actor_id="reviewer")
            self.assertEqual(record.status, status)
        executed = (base.transition_status("approved", changed_at="2026-11-08T10:01:00Z",
                                           actor_id="reviewer")
                    .transition_status("executed", changed_at="2026-11-08T10:02:00Z",
                                       actor_id="operator"))
        self.assertEqual(DecisionRecord.from_dict(executed.to_dict()), executed)
        with self.assertRaises(DecisionTransitionError):
            base.transition_status("executed", changed_at="2026-11-08T10:01:00Z",
                                   actor_id="operator")
        approved = base.transition_status("approved", changed_at="2026-11-08T10:01:00Z",
                                          actor_id="reviewer")
        with self.assertRaises(DecisionTransitionError):
            approved.transition_status("proposed", changed_at="2026-11-08T10:02:00Z",
                                       actor_id="reviewer")
        self.assertEqual(base.status, "proposed")
        self.assertEqual(base.status_history, ())
        discontinuous = executed.to_dict()
        discontinuous["status_history"][1]["from_status"] = "proposed"
        discontinuous["status_history"][1]["to_status"] = "approved"
        with self.assertRaisesRegex(ValueError, "contiguous"):
            DecisionRecord.from_dict(discontinuous)

    def test_rejects_non_scalar_or_non_finite_constraints(self) -> None:
        with self.assertRaisesRegex(TypeError, "JSON scalar"):
            DecisionRecord("d1", "tenant-1", "agent-1", "2026-11-08T10:00:00Z",
                           "goal", (DecisionOption("a", "A"),), None,
                           (), {"nested": {"unsafe": True}})
        with self.assertRaisesRegex(ValueError, "finite"):
            DecisionRecord("d1", "tenant-1", "agent-1", "2026-11-08T10:00:00Z",
                           "goal", (DecisionOption("a", "A"),), None,
                           (), {"threshold": float("inf")})


class DecisionLedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.log = EventLog()
        self.ledger = DecisionLedger(self.log, lambda: 1_800_000_000_000)
        self.evidence = EvidenceVersion("m1", 2)
        self.decision = DecisionRecord(
            "d1", "tenant-1", "agent-1", "2026-11-08T10:00:00Z", "choose",
            (DecisionOption("a", "A", (self.evidence,)),), "a", (self.evidence,), {},
        )

    def tearDown(self) -> None:
        self.log.close()

    def test_graph_keeps_seen_reliance_authorization_and_execution_distinct(self) -> None:
        self.ledger.record(self.decision)
        exposure = self.log.append(Event(
            EventType.EXPOSURE_DECIDED, 2,
            {"memory_id": "m1", "version": 2, "exposed": True, "propensity": 1.0},
            agent_id="agent-1",
        ))
        self.ledger.observe("d1", exposure.event_id, actor_id="agent-1",
                            recorded_at="2026-11-08T10:01:00Z")
        for relation, target in (("relied_on", "claim-1"),
                                 ("authorized", "effect:1"), ("executed", "effect:1")):
            self.ledger.link(DecisionEdge(f"edge-{relation}", "d1", relation, target,
                                          "agent-1", "2026-11-08T10:02:00Z",
                                          self.evidence if relation == "relied_on" else None))
        graph = self.ledger.graph("d1")
        self.assertEqual(len(graph.seen), 1)
        self.assertEqual(graph.seen[0].exposure_event_id, exposure.event_id)
        self.assertEqual(len(graph.relied_on), 1)
        self.assertEqual(graph.relied_on[0].target_id, "claim-1")
        self.assertEqual(len(graph.authorized), 1)
        self.assertEqual(len(graph.executed), 1)
        self.assertNotEqual(graph.authorized[0].edge_id, graph.executed[0].edge_id)
        with self.assertRaisesRegex(DecisionEdgeError, "edge_id already exists"):
            self.ledger.link(graph.relied_on[0])
        with self.assertRaisesRegex(DecisionEdgeError, "decision_id already exists"):
            self.ledger.record(self.decision)

    def test_ledger_replays_from_fresh_log_and_rejects_false_seen_or_unlinked_evidence(self) -> None:
        self.ledger.record(self.decision)
        replay = DecisionLedger(self.log, lambda: 1_800_000_000_000)
        self.assertEqual(replay.get("d1"), self.decision)
        with self.assertRaisesRegex(DecisionEdgeError, "listed by the decision"):
            replay.link(DecisionEdge("bad", "d1", "relied_on", "claim",
                                     "agent-1", "2026-11-08T10:02:00Z",
                                     EvidenceVersion("other", 1)))
        withheld = self.log.append(Event(
            EventType.EXPOSURE_DECIDED, 3,
            {"memory_id": "m1", "version": 2, "exposed": False, "propensity": 0.2},
        ))
        with self.assertRaisesRegex(DecisionEdgeError, "cannot be marked seen"):
            replay.observe("d1", withheld.event_id, actor_id="agent-1",
                           recorded_at="2026-11-08T10:03:00Z")
        wrong_actor = self.log.append(Event(
            EventType.EXPOSURE_DECIDED, 4,
            {"memory_id": "m1", "version": 2, "exposed": True, "propensity": 1.0},
            agent_id="another-agent",
        ))
        with self.assertRaisesRegex(DecisionEdgeError, "actor must match"):
            replay.observe("d1", wrong_actor.event_id, actor_id="agent-1",
                           recorded_at="2026-11-08T10:04:00Z")

    def test_typed_edges_require_evidence_only_for_reliance(self) -> None:
        with self.assertRaisesRegex(DecisionEdgeError, "exact evidence"):
            DecisionEdge("e1", "d1", "relied_on", "claim", "agent-1",
                         "2026-11-08T10:00:00Z")
        with self.assertRaisesRegex(DecisionEdgeError, "cannot carry"):
            DecisionEdge("e2", "d1", "executed", "effect:1", "agent-1",
                         "2026-11-08T10:00:00Z", self.evidence)


if __name__ == "__main__":
    unittest.main()

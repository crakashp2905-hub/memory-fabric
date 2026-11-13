"""CDM contracts validate canonical data and remain inert on import."""

from __future__ import annotations

import unittest
import json

from memory_fabric.causal_replay.types import (BeliefReference, CDMError, ReplayContext,
                                                DecisionRecord, ModelProvenance,
                                                ToolObservation,
                                                canonical_json, digest_json,
                                                parse_record, schema_is_compatible,
                                                schema_version, serialize_record)


class TestCanonical(unittest.TestCase):
    def test_schema_major_minor_rules_are_explicit(self):
        self.assertEqual(schema_version("memory-fabric-cdm-v1"), (1, 0))
        self.assertEqual(schema_version("memory-fabric-cdm-v1.0"), (1, 0))
        self.assertTrue(schema_is_compatible("memory-fabric-cdm-v1.0"))
        self.assertFalse(schema_is_compatible("memory-fabric-cdm-v1.1"))
        self.assertFalse(schema_is_compatible("memory-fabric-cdm-v2"))
        with self.assertRaises(CDMError):
            schema_version("memory-fabric-cdm-v01")

    def test_map_order_is_stable(self):
        self.assertEqual(canonical_json({"b": 2, "a": 1}), '{"a":1,"b":2}')
        self.assertEqual(digest_json({"a": 1, "b": 2}), digest_json({"b": 2, "a": 1}))

    def test_reject_nonfinite_deep_and_nonstring_keys(self):
        deep = 0
        for _ in range(66):
            deep = [deep]
        for value in (float("nan"), {1: "bad"}, deep):
            with self.assertRaises(CDMError):
                canonical_json(value)


class TestContracts(unittest.TestCase):
    def test_model_decision_requires_complete_versioned_runtime_provenance(self):
        evidence = (BeliefReference("m_1", 2, "tenant_a", "a" * 64),)
        with self.assertRaises(CDMError):
            DecisionRecord(8, "tenant_a", "agent_a", ("monitor", "investigate"),
                "investigate", evidence, "policy-v1", "b" * 64,
                execution_mode="model")
        provenance = ModelProvenance(
            "local-model", "checkpoint-4", "c" * 64,
            "ollama-runtime", "0.13.2", "d" * 64,
        )
        record = DecisionRecord(8, "tenant_a", "agent_a", ("monitor", "investigate"),
            "investigate", evidence, "policy-v1", "b" * 64,
            execution_mode="model", model_provenance=provenance)
        restored = parse_record(DecisionRecord, serialize_record(record))
        self.assertEqual(restored, record)
        with self.assertRaises(CDMError):
            ModelProvenance("local-model", "checkpoint-4", "not-a-digest",
                            "ollama-runtime", "0.13.2", "d" * 64)

    def test_tool_observation_determinism_classes_are_closed(self):
        for determinism in ("exogenous", "simulated_endogenous", "opaque"):
            observation = ToolObservation("agent", "tool", "a" * 64, "b" * 64,
                                          "c" * 64, determinism)
            self.assertEqual(parse_record(ToolObservation,
                serialize_record(observation)).determinism, determinism)
        with self.assertRaises(CDMError):
            ToolObservation("agent", "tool", "a" * 64, "b" * 64, "c" * 64,
                            "seeded-but-unknown")

    def test_context_separates_sequence_and_valid_time(self):
        context = ReplayContext(known_at=10, valid_at=123, wall_clock_ms=456)
        self.assertEqual((context.known_at, context.valid_at, context.wall_clock_ms), (10, 123, 456))
        with self.assertRaises(CDMError):
            ReplayContext(known_at=True)

    def test_reference_binds_tenant_version_and_digest(self):
        ref = BeliefReference("m_1", 2, "tenant_a", "a" * 64)
        self.assertEqual(ref.version, 2)
        with self.assertRaises(CDMError):
            BeliefReference("m_1", 0, "tenant_a", "a" * 64)

    def test_registered_record_roundtrip_and_unknown_field_refusal(self):
        record = DecisionRecord(8, "tenant_a", "agent_a", ("monitor", "investigate"),
            "investigate", (BeliefReference("m_1", 2, "tenant_a", "a" * 64),),
            "policy-v1", "b" * 64)
        restored = parse_record(DecisionRecord, serialize_record(record))
        self.assertEqual(restored, record)
        compatible_minor_spelling = json.loads(serialize_record(record))
        compatible_minor_spelling["schema"] = "memory-fabric-cdm-v1.0"
        self.assertEqual(parse_record(DecisionRecord, compatible_minor_spelling), record)
        for schema in ("memory-fabric-cdm-v1.1", "memory-fabric-cdm-v2"):
            with self.subTest(schema=schema), self.assertRaises(CDMError):
                parse_record(DecisionRecord, {**compatible_minor_spelling, "schema": schema})
        payload = record.to_dict() if hasattr(record, "to_dict") else {
            "sequence": record.sequence, "tenant_id": record.tenant_id,
            "agent_id": record.agent_id, "options": list(record.options),
            "selected": record.selected, "evidence": [record.evidence[0].__dict__],
            "policy_id": record.policy_id, "policy_digest": record.policy_digest,
            "schema": record.schema}
        payload["unexpected"] = True
        with self.assertRaises(CDMError):
            parse_record(DecisionRecord, payload)


if __name__ == "__main__":
    unittest.main()

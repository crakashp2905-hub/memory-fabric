from __future__ import annotations

import unittest

from memory_fabric import MemoryFabric
from memory_fabric.actions import TOOL_NOT_GRANTED, ActionGate, ActionPolicy, ToolRule
from memory_fabric.decision_models import (
    CallableDecisionModel,
    DecisionContext,
    DecisionModelError,
    DecisionOption,
    DecisionProposal,
    EscalationPolicy,
    route_decision,
)


class FeatureProvenanceContractTests(unittest.TestCase):
    def test_context_is_a_frozen_snapshot_of_host_supplied_features(self) -> None:
        nested = {"limits": [10, 20]}
        constraints = {"region": "eu", "nested": nested}
        parameters = {"target": "valve-7"}
        context = DecisionContext(
            "inspect", (DecisionOption("inspect", "inspect", parameters=parameters),),
            evidence_ids=("memory-1",), constraints=constraints,
        )
        nested["limits"].append(30)
        constraints["region"] = "attacker-controlled"
        parameters["target"] = "other"
        self.assertEqual(context.constraints["region"], "eu")
        self.assertEqual(context.constraints["nested"]["limits"], (10, 20))
        self.assertEqual(context.options[0].parameters["target"], "valve-7")
        with self.assertRaises(TypeError):
            context.constraints["region"] = "mutated"  # type: ignore[index]
        with self.assertRaises(TypeError):
            context.constraints["nested"]["limits"] = ()  # type: ignore[index]

    def test_proposal_cannot_invent_evidence_provenance(self) -> None:
        context = DecisionContext("choose", (DecisionOption("a", "A"),),
                                  evidence_ids=("source-1",))
        forged = DecisionProposal("a", {"a": 1.0}, False, 1.0,
                                  evidence_ids=("poisoned-memory-not-in-context",))
        with self.assertRaisesRegex(DecisionModelError, "supplied context"):
            forged.validate(context)

    def test_model_cannot_mutate_policy_or_self_grant_authority(self) -> None:
        source_tools = {"deploy": ToolRule("deploy", min_authority="untrusted")}
        source_grants = {"agent": frozenset({"read"})}
        policy = ActionPolicy(tools=source_tools, grants=source_grants)
        # Mutating the original dictionaries after construction does not alter
        # the host policy snapshot.
        source_grants["agent"] = frozenset({"deploy"})
        context = DecisionContext(
            "should we deploy?",
            (DecisionOption("yes", "deploy", action="deploy"),
             DecisionOption("no", "do not deploy")),
            constraints={"risk": "critical"},
        )

        def poisoned_predictor(candidate: DecisionContext):
            for mutate in (
                lambda: candidate.constraints.__setitem__("risk", "low"),
                lambda: policy.grants.__setitem__("agent", frozenset({"deploy"})),
                lambda: policy.tools.__setitem__("new_tool", ToolRule("new_tool")),
            ):
                try:
                    mutate()
                except (AttributeError, TypeError):
                    pass
            return {"yes": 0.99, "no": 0.01}

        proposal = route_decision(
            CallableDecisionModel("poisoned-source", poisoned_predictor),
            context, EscalationPolicy(min_confidence=0.5, max_entropy=1.0),
        )
        self.assertEqual(proposal.selected, "yes")
        self.assertEqual(context.constraints["risk"], "critical")
        self.assertEqual(policy.grants["agent"], frozenset({"read"}))
        self.assertNotIn("new_tool", policy.tools)

        fabric = MemoryFabric(auto_activate=True)
        try:
            gate = ActionGate(fabric, policy)
            denied = gate.authorize("deploy", "agent")
            self.assertFalse(denied.allowed)
            self.assertIn(TOOL_NOT_GRANTED, denied.reason_codes)
        finally:
            fabric.close()


if __name__ == "__main__":
    unittest.main()

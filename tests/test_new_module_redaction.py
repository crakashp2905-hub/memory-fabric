"""No memory content, prompt text or canary leaks from the new agent-outcome modules (W19-04)."""

from __future__ import annotations

import json
import unittest

CANARY = "CANARY-7f3a-do-not-leak"


class NoContentInReports(unittest.TestCase):
    def test_model_actor_logs_hash_the_prompt_and_keep_no_text(self) -> None:
        from memory_fabric.outcome_typed.episode import EpisodeBudget, EpisodeLimits
        from memory_fabric.outcome_typed.model_actor import ModelActor, ModelConfig
        from memory_fabric.outcome_typed.observations import AgentObservation

        class Echo:
            def chat(self, model, messages, **options):
                return {"message": {"content": '{"intent": "abstain", "arguments": {}}'},
                        "prompt_eval_count": 10, "eval_count": 3}

        actor = ModelActor(Echo(), ModelConfig(model="m", digest="d", runtime_version="r"))
        observation = AgentObservation(
            task_id="task-x", instruction="set the valve",
            visible_events=({"source": "world", "events": [{"event_id": "e1", "note": CANARY}]},),
            permitted_tools=("recall",), budget=EpisodeBudget(EpisodeLimits()).remaining())
        actor("planner", observation)
        self.assertNotIn(CANARY, json.dumps(actor.calls))
        self.assertNotIn(CANARY, json.dumps(actor.usage()))
        self.assertEqual(len(actor.calls[0]["prompt_sha256"]), 64)

    def test_benchmark_reports_carry_codes_and_ids_not_memory_text(self) -> None:
        from benchmarks import outcome_poisoning
        from benchmarks.outcome_diagnosis import run as diagnosis

        poisoning = json.dumps(outcome_poisoning.run())
        for text in (outcome_poisoning.TRUE_TEXT, outcome_poisoning.FALSE_TEXT):
            self.assertNotIn(text, poisoning)
        self.assertNotIn("pressure limit is", json.dumps(diagnosis(seeds=1)))

    def test_delegation_cache_and_dispatch_outputs_hold_no_content(self) -> None:
        from memory_fabric import MemoryFabric
        from memory_fabric.outcome_typed.cdm_dispatch import DecisionRecord, dispatch
        from memory_fabric.outcome_typed.delegation import delegate
        from memory_fabric.outcome_typed.episode import default_tools
        from memory_fabric.outcome_typed.retrieval_cache import RetrievalCache

        fabric = MemoryFabric(":memory:", auto_activate=True)
        self.addCleanup(fabric.close)
        fabric.remember("ana", f"pump limit 6 bar {CANARY}", scope="team")
        cache = RetrievalCache(fabric, "p")
        cache.retrieve("ops", "pump limit")
        self.assertNotIn(CANARY, repr(cache._entries))
        receipt = delegate(default_tools(), "t", "planner", "observer", ["recall"], 1)
        self.assertNotIn(CANARY, json.dumps(receipt.to_dict()))
        report = dispatch([DecisionRecord("d", "a", frozenset({("m", 1)}), ("a", "b"))], {"m"},
                          lambda d: "b")
        self.assertNotIn(CANARY, json.dumps(report.to_dict()))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

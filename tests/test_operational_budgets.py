from __future__ import annotations

import unittest
from unittest.mock import patch

from memory_fabric import MemoryFabric, LifecycleState
from memory_fabric.agent_api import RateLimit, WorkerBudget, request_length_allowed
from memory_fabric.governance.retention import RetentionDecision
from memory_fabric.limits import LimitExceeded, Limits
from memory_fabric.cli import build_parser


class OperationalBudgets(unittest.TestCase):
    def test_safe_defaults_are_finite_and_invalid_settings_fail_at_construction(self) -> None:
        defaults = Limits()
        self.assertEqual(defaults.max_memories, 1_000_000)
        self.assertEqual(defaults.max_retention_actions, 1_000)
        server = RateLimit()
        self.assertEqual(server.max_request_bytes, 64 * 1024)
        self.assertEqual(server.max_workers, 32)
        cli = build_parser().parse_args(["agent-api", "--agents-file", "agents.txt"])
        self.assertEqual((cli.max_memories, cli.max_retention_actions,
                          cli.max_request_bytes, cli.max_workers),
                         (1_000_000, 1_000, 64 * 1024, 32))
        for kwargs in ({"max_content_bytes": 0}, {"window_ms": 0},
                       {"max_memories": 0}, {"max_retention_actions": 0},
                       {"max_memories": True}, {"max_retention_actions": 1.5}):
            with self.subTest(kwargs), self.assertRaises(ValueError):
                Limits(**kwargs)
        for kwargs in ({"max_request_bytes": 0}, {"max_workers": 0}, {"max_buckets": 0},
                       {"max_request_bytes": True}, {"max_workers": 1.5}):
            with self.subTest(kwargs), self.assertRaises(ValueError):
                RateLimit(**kwargs)

    def test_store_memory_count_cap_refuses_without_partial_state(self) -> None:
        with MemoryFabric(":memory:", limits=Limits(max_memories=1)) as fabric:
            fabric.remember("agent", "first memory")
            before = fabric.log.head_seq
            with self.assertRaises(LimitExceeded) as caught:
                fabric.remember("agent", "second memory")
            self.assertEqual(caught.exception.code, "memory_budget_exhausted")
            self.assertEqual(len(fabric.state.memories), 1)
            self.assertEqual(fabric.log.head_seq, before)

    def test_retention_apply_caps_batch_and_prioritizes_nonterminal_deprecation(self) -> None:
        with MemoryFabric(":memory:", auto_activate=True,
                          limits=Limits(max_retention_actions=1)) as fabric:
            ids = [fabric.remember("agent", f"retention fixture {n}", scope="team")
                   for n in range(3)]
            decisions = [RetentionDecision(ids[0], "delete", "terminal"),
                         RetentionDecision(ids[1], "deprecate", "nonterminal"),
                         RetentionDecision(ids[2], "deprecate", "nonterminal")]
            with patch.object(fabric.retention, "sweep", return_value=decisions):
                applied = fabric.sweep_retention(apply=True)
            self.assertEqual(len(applied), 1)
            self.assertEqual(applied[0].action, "deprecate")
            self.assertEqual(applied[0].memory_id, min(ids[1:]))
            self.assertEqual(fabric.state.memories[ids[0]].lifecycle_state,
                             LifecycleState.ACTIVE)

    def test_request_byte_limit_includes_boundary_and_rejects_invalid_lengths(self) -> None:
        self.assertTrue(request_length_allowed(64, 64))
        self.assertTrue(request_length_allowed(0, 64))
        self.assertFalse(request_length_allowed(65, 64))
        self.assertFalse(request_length_allowed(-1, 64))
        with self.assertRaises(ValueError):
            request_length_allowed(1, 0)

    def test_worker_budget_refuses_excess_concurrency_without_waiting(self) -> None:
        workers = WorkerBudget(2)
        self.assertTrue(workers.try_acquire())
        self.assertTrue(workers.try_acquire())
        self.assertFalse(workers.try_acquire())
        workers.release()
        self.assertTrue(workers.try_acquire())
        workers.release()
        workers.release()


if __name__ == "__main__":
    unittest.main()

"""Job spool (W17-04, W18-08) and storage transaction benchmark (W17-07)."""

from __future__ import annotations

import threading
import unittest

from memory_fabric.outcome_typed.spool import DEAD, DONE, READY, JobSpool, SpoolFull


class Spool(unittest.TestCase):
    def setUp(self) -> None:
        self.spool = JobSpool(max_attempts=2, max_depth=3)
        self.addCleanup(self.spool.close)

    def test_one_live_lease_per_job_and_a_stale_worker_cannot_settle(self) -> None:
        self.spool.enqueue("j1", {"replay": "d1"})
        first = self.spool.lease("w1", now_ms=0, ttl_ms=100)
        self.assertIsNotNone(first)
        self.assertIsNone(self.spool.lease("w2", now_ms=50, ttl_ms=100))  # still leased
        second = self.spool.lease("w2", now_ms=150, ttl_ms=100)  # w1's lease expired
        assert first is not None and second is not None
        self.assertEqual(second.job_id, "j1")
        self.assertFalse(self.spool.complete(first, now_ms=160))
        self.assertIsNone(self.spool.heartbeat(first, now_ms=160, ttl_ms=100))
        self.assertTrue(self.spool.complete(second, now_ms=160))
        self.assertEqual(self.spool.state("j1")["state"], DONE)

    def test_heartbeat_extends_only_the_holder(self) -> None:
        self.spool.enqueue("j1", {})
        lease = self.spool.lease("w1", now_ms=0, ttl_ms=100)
        assert lease is not None
        renewed = self.spool.heartbeat(lease, now_ms=90, ttl_ms=100)
        self.assertIsNotNone(renewed)
        self.assertIsNone(self.spool.lease("w2", now_ms=150, ttl_ms=100))

    def test_retry_budget_then_dead_letter(self) -> None:
        self.spool.enqueue("j1", {})
        lease = self.spool.lease("w1", now_ms=0, ttl_ms=100)
        assert lease is not None
        self.assertEqual(self.spool.fail(lease, now_ms=10, error="model timeout"), READY)
        lease = self.spool.lease("w1", now_ms=20, ttl_ms=100)
        assert lease is not None
        self.assertEqual(self.spool.fail(lease, now_ms=30, error="model timeout"), DEAD)
        self.assertEqual(self.spool.dead_letters(), ["j1"])
        self.assertIsNone(self.spool.lease("w1", now_ms=40, ttl_ms=100))

    def test_depth_cap_gives_backpressure(self) -> None:
        for index in range(3):
            self.spool.enqueue(f"j{index}", {})
        with self.assertRaises(SpoolFull):
            self.spool.enqueue("j3", {})
        self.assertEqual(self.spool.depth(), 3)

    def test_a_lease_never_authorizes_an_effect(self) -> None:
        self.spool.enqueue("j1", {})
        lease = self.spool.lease("w1", now_ms=0, ttl_ms=100)
        assert lease is not None
        self.assertFalse(lease.authorizes_effects)

    def test_concurrent_workers_never_share_a_job(self) -> None:
        spool = JobSpool(max_attempts=1, max_depth=100)
        self.addCleanup(spool.close)
        for index in range(40):
            spool.enqueue(f"j{index}", {})
        taken: list[str] = []
        guard = threading.Lock()

        def worker(name: str) -> None:
            while (lease := spool.lease(name, now_ms=0, ttl_ms=10_000)) is not None:
                with guard:
                    taken.append(lease.job_id)

        threads = [threading.Thread(target=worker, args=(f"w{i}",)) for i in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(sorted(taken), sorted(f"j{i}" for i in range(40)))


class StorageBenchmark(unittest.TestCase):
    def test_sqlite_scenario_is_consistent_and_postgres_says_not_run_without_a_dsn(self) -> None:
        import os

        from benchmarks.outcome_storage_bench import run

        report = run(threads=3, per_thread=10)
        sqlite = report["backends"]["sqlite"]
        self.assertTrue(sqlite["consistent"])
        self.assertTrue(sqlite["sequences_unique"])
        self.assertTrue(sqlite["sequences_gapless"])
        self.assertTrue(sqlite["chain_verifies"])
        if not os.environ.get("MEMORY_FABRIC_TEST_PG"):
            self.assertEqual(report["backends"]["postgres"]["status"], "NOT_RUN")
        else:  # pragma: no cover - the Postgres CI job
            self.assertTrue(report["backends"]["postgres"]["consistent"])
        self.assertIn("this host only", report["scope"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

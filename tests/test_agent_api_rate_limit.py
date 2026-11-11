from __future__ import annotations

import unittest

from memory_fabric import MemoryFabric
from memory_fabric.agent_api import AgentApi, RateLimit, _ApiError, encode_credential
from memory_fabric.limits import LimitExceeded, Limits
from memory_fabric.service import MemoryService

OBSERVED: dict[str, dict[str, int | bool]] = {}


class Clock:
    def __init__(self) -> None:
        self.value = 100.0

    def __call__(self) -> float:
        return self.value


class AgentApiRateLimits(unittest.TestCase):
    def setUp(self) -> None:
        self.clock = Clock()
        self.fabric = MemoryFabric(":memory:", auto_activate=True)
        self.addCleanup(self.fabric.close)
        self.service = MemoryService(fabric=self.fabric)
        self.service.register_agent("agent-a", key=b"A" * 32, tenant_id="tenant-a")
        self.credentials = [encode_credential(self.service.issue("agent-a", ttl_seconds=600))
                            for _ in range(128)]

    def test_credential_cycling_cannot_reset_agent_rate_budget_or_write(self) -> None:
        api = AgentApi(self.service, limits=RateLimit(rate=1.0, burst=2, auth_failures=1.0),
                       clock=self.clock)
        for index, credential in enumerate(self.credentials[:2]):
            result = api.handle("remember", credential, {"content": f"accepted {index}"})
            self.assertEqual(result["state"], "active")
        before = (self.fabric.log.head_seq, set(self.fabric.state.memories))

        for credential in self.credentials[2:]:
            with self.assertRaises(_ApiError) as caught:
                api.handle("remember", credential, {"content": "must not be written"})
            self.assertEqual(caught.exception.status, 429)
            self.assertGreater(caught.exception.retry_after or 0, 0)

        self.assertEqual((self.fabric.log.head_seq, set(self.fabric.state.memories)), before)
        self.assertEqual(len(api._per_agent._buckets), 1,
                         "all credentials for the same agent share one bounded bucket")
        OBSERVED["credential_rate_limit"] = {
            "credentials": len(self.credentials), "accepted_writes": 2,
            "rejected_requests": len(self.credentials) - 2,
            "agent_bucket_count": len(api._per_agent._buckets),
            "rejections_changed_store": False,
        }

    def test_store_write_quota_refusals_make_no_partial_events(self) -> None:
        limited = MemoryFabric(":memory:", auto_activate=True,
                               limits=Limits(writes_per_window=2, window_ms=60_000))
        self.addCleanup(limited.close)
        service = MemoryService(fabric=limited)
        service.register_agent("agent-a", key=b"A" * 32, tenant_id="tenant-a")
        credentials = [encode_credential(service.issue("agent-a", ttl_seconds=600))
                       for _ in range(32)]
        api = AgentApi(service, limits=RateLimit(rate=100.0, burst=100, auth_failures=5.0),
                       clock=self.clock)
        for index, credential in enumerate(credentials[:2]):
            api.handle("remember", credential, {"content": f"quota write {index}"})
        before = (limited.log.head_seq, set(limited.state.memories))

        for credential in credentials[2:]:
            with self.assertRaises(LimitExceeded) as caught:
                api.handle("remember", credential, {"content": "quota rejected"})
            self.assertEqual(caught.exception.code, "write_quota_exhausted")

        self.assertEqual((limited.log.head_seq, set(limited.state.memories)), before)
        self.assertEqual(len(limited.limits._seen), 1)
        self.assertEqual(len(api._per_agent._buckets), 1)
        OBSERVED["store_write_quota"] = {
            "credentials": len(credentials), "accepted_writes": 2,
            "quota_rejections": len(credentials) - 2,
            "quota_counter_agents": len(limited.limits._seen),
            "rejections_changed_store": False,
        }

    def test_auth_failure_buckets_stay_bounded_under_address_cycling(self) -> None:
        api = AgentApi(self.service, limits=RateLimit(rate=10.0, burst=10,
                                                       auth_failures=1.0, max_buckets=16),
                       clock=self.clock)
        before = self.fabric.log.head_seq
        for index in range(500):
            with self.assertRaises(_ApiError) as caught:
                api.precheck("invalid", remote=f"192.0.2.{index}")
            self.assertIn(caught.exception.status, (401, 429))
        self.assertEqual(len(api._per_address._buckets), 16)
        self.assertLessEqual(len(api._per_address._buckets), api._per_address.max_keys)
        self.assertEqual(self.fabric.log.head_seq, before)
        self.assertEqual(self.fabric.state.memories, {})
        OBSERVED["address_bucket_bound"] = {
            "cycled_addresses": 500, "bucket_count": len(api._per_address._buckets),
            "bucket_max_keys": api._per_address.max_keys,
            "rejections_changed_store": False,
        }


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

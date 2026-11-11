import unittest

from memory_fabric import MemoryFabric
from memory_fabric.enforcement import WRONG_TENANT, Verdict


class TestTenantEnforcement(unittest.TestCase):
    def test_wrong_tenant_is_refused_even_when_concealment_is_disabled(self) -> None:
        fabric = MemoryFabric(":memory:", auto_activate=True, conceal_cross_tenant=False)
        self.addCleanup(fabric.close)
        memory_id = fabric.remember("alice", "private tenant detail", tenant_id="tenant-b")

        decision = fabric.enforcer.check(memory_id, tenant_id="tenant-a")

        self.assertEqual(decision.verdict, Verdict.DENY)
        self.assertEqual(decision.reason_code, WRONG_TENANT)
        self.assertEqual(decision.version, 0)
        self.assertEqual(decision.detail, "")

"""Prometheus metrics from the log, incrementally; no content, no agent ids."""

from __future__ import annotations

import unittest

from memory_fabric import MemoryFabric
from memory_fabric.actions import ActionGate, ActionPolicy, ToolRule
from memory_fabric.observability.metrics import StoreMetrics
from memory_fabric.observability.server import Api


class TestMetrics(unittest.TestCase):
    def test_counts_and_stays_incremental(self):
        f = MemoryFabric(":memory:", auto_activate=True)
        self.addCleanup(f.close)
        mid = f.remember("ag_secretive", "Pump P-14 relief valve is set to 12 bar.", scope="team")
        f.retrieve("ag_reader", "relief valve", k=3)
        gate = ActionGate(f, ActionPolicy(tools={"set_relief": ToolRule("set_relief")},
                                          grants={"ag_ops": frozenset({"set_relief"})}))
        cert = f.certify("x", [mid], "ag_ops")
        gate.authorize("set_relief", "ag_ops", cert)
        m = StoreMetrics()
        text = m.render(f)
        self.assertIn('mf_memories{state="active"} 1', text)
        self.assertIn("mf_retrievals_total 1", text)
        self.assertIn('mf_actions_total{tool="set_relief",allowed="true"} 1', text)
        f.quarantine(mid, reason="wrong", actor="lead", basis="contradicted")
        gate.authorize("set_relief", "ag_ops", cert)
        text = m.render(f)
        self.assertIn('mf_actions_total{tool="set_relief",allowed="false"} 1', text)
        self.assertIn('mf_withdrawals_total{to="quarantined"} 1', text)
        self.assertNotIn("Pump", text)
        self.assertNotIn("ag_secretive", text)
        self.assertNotIn(mid, text)

    def test_sparse_tenant_activity_does_not_create_tenant_labels_or_content(self):
        f = MemoryFabric(":memory:", auto_activate=True)
        self.addCleanup(f.close)
        rare_id = f.remember(
            "rare_tenant_agent", "UNIQUE-CANARY-9917 sparse activity marker",
            tenant_id="tenant_rare", scope="team")
        f.remember("common_tenant_agent", "ordinary shared activity",
                   tenant_id="tenant_common", scope="team")
        f.retrieve("rare_tenant_agent", "sparse activity", k=3)
        metrics = StoreMetrics().render(f)
        dashboard = Api(f)
        overview = dashboard.handle("/api/overview", {})
        visible = metrics + repr(overview)
        for marker in ("tenant_rare", "rare_tenant_agent", "UNIQUE-CANARY-9917", rare_id):
            self.assertNotIn(marker, visible)
        self.assertIn("mf_writes_total 2", metrics)
        self.assertIn("mf_retrievals_total 1", metrics)

    def test_served_through_the_dashboard_api(self):
        f = MemoryFabric(":memory:", auto_activate=True)
        self.addCleanup(f.close)
        self.assertIn("mf_events_total", Api(f).metrics_text())


if __name__ == "__main__":
    unittest.main()

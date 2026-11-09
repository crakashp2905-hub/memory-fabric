from __future__ import annotations

import unittest

from memory_fabric import MemoryFabric
from memory_fabric.agent_api import AgentApi, _ApiError, encode_credential
from memory_fabric.adapters.mcp import McpServer
from memory_fabric.fabric import NotFound
from memory_fabric.observability.control import eligibility
from memory_fabric.sdk import NotUsable, agent
from memory_fabric.service import MemoryService
from memory_fabric.typed_query import select


class CrossTenantSurfaceMatrix(unittest.TestCase):
    def test_foreign_ids_are_opaque_and_writes_stay_in_the_bound_tenant(self) -> None:
        fabric = MemoryFabric(":memory:", auto_activate=True)
        self.addCleanup(fabric.close)
        self.assertTrue(fabric.conceal_cross_tenant)
        foreign_text = "TENANT-A-SECRET-CANARY-8421 controls pump P-77"
        foreign = fabric.remember(
            "agent_a", foreign_text, tenant_id="tn_a", scope="team",
            structured={"project_code": "A-ONLY-991"})
        fabric.validate(foreign, actor="reviewer")
        fabric.share(foreign, "team", actor="reviewer")
        local = fabric.remember(
            "agent_b", "Tenant B local record", tenant_id="tn_b", scope="team",
            structured={"project_code": "B-ONLY-112"})
        fabric.validate(local, actor="reviewer")
        missing = "01NOTAREALMEMORYID00000000"

        # SDK: recall, fetch and writes remain tenant-bound; delete is not an
        # agent capability. A foreign id and a missing id have the same denial.
        sdk = agent(fabric, "agent_b", "tn_b")
        self.assertNotIn(foreign, [row.memory_id for row in sdk.recall("pump P-77")])
        with self.assertRaises(NotUsable) as foreign_read:
            sdk.fetch(foreign)
        with self.assertRaises(NotUsable) as missing_read:
            sdk.fetch(missing)
        self.assertEqual(foreign_read.exception.decision.reason_code,
                         missing_read.exception.decision.reason_code)
        with self.assertRaises(TypeError):
            sdk.remember("attempt scope override", tenant_id="tn_a")
        self.assertFalse(hasattr(sdk, "delete"))
        self.assertFalse(hasattr(sdk, "retract"))

        # Inference through the tenant view cannot use a foreign premise.
        view = fabric.for_tenant("tn_b", "agent_b")
        with self.assertRaises(NotFound):
            view.derive("agent B inference", parents=[foreign])

        # HTTP request handling is exercised without opening a local socket.
        service = MemoryService(fabric=fabric)
        service.register_agent("agent_b", key=b"tenant-b-key", tenant_id="tn_b")
        bearer = encode_credential(service.issue("agent_b"))
        api = AgentApi(service)
        responses = []
        for memory_id in (foreign, missing):
            try:
                api.handle("fetch", bearer, {"memory_id": memory_id})
            except _ApiError as exc:
                responses.append((exc.status, exc.message.replace(memory_id, "<id>")))
        self.assertEqual(responses[0], responses[1])
        recalled = api.handle("recall", bearer, {"query": "TENANT-A-SECRET-CANARY-8421"})
        self.assertNotIn(foreign_text, str(recalled))
        http_write = api.handle("remember", bearer, {"content": "Tenant B HTTP write"})
        self.assertEqual(fabric.tenant_of(http_write["memory_id"]), "tn_b")
        for operation in ("delete", "infer"):
            with self.assertRaises(_ApiError) as denied:
                api.handle(operation, bearer, {})
            self.assertEqual(denied.exception.status.value, 404)

        # MCP: identity is fixed when the server is constructed. Unknown
        # tenant/scope fields cannot move a write to tenant A.
        mcp = McpServer(sdk, fabric)
        tool_names = {tool["name"] for tool in mcp.tools()}
        self.assertFalse({"delete", "retract", "infer"} & tool_names)
        foreign_tool, foreign_error = mcp.call("fetch", {"memory_id": foreign})
        missing_tool, missing_error = mcp.call("fetch", {"memory_id": missing})
        self.assertTrue(foreign_error and missing_error)
        self.assertEqual(foreign_tool["error"].replace(foreign, "<id>"),
                         missing_tool["error"].replace(missing, "<id>"))
        mcp_write, write_error = mcp.call("remember", {
            "content": "Tenant B MCP write", "tenant_id": "tn_a", "scope": "team"})
        self.assertFalse(write_error)
        self.assertEqual(fabric.tenant_of(mcp_write["memory_id"]), "tn_b")

        # Typed query counts only the caller's tenant. Dashboard eligibility
        # hides a foreign id with the same shape as a missing id.
        query = select(fabric, "agent_b", {"project_code": "A-ONLY-991"}, tenant_id="tn_b")
        self.assertEqual(query.ids, [])
        self.assertEqual(query.considered, sum(
            memory.tenant_id == "tn_b" for memory in fabric.state.memories.values()))
        foreign_dashboard = eligibility(fabric, foreign, "agent_b", "tn_b")
        missing_dashboard = eligibility(fabric, missing, "agent_b", "tn_b")
        self.assertEqual(
            {**foreign_dashboard, "memory_id": "<requested-id>"},
            {**missing_dashboard, "memory_id": "<requested-id>"},
        )
        self.assertNotIn("tn_a", str(foreign_dashboard))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

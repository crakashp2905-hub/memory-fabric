"""Request-stage traces reconcile and cover the HTTP and store boundaries."""

from __future__ import annotations

import json
import threading
import unittest
import urllib.request

from memory_fabric import MemoryFabric
from memory_fabric.agent_api import (
    AgentApi,
    AgentEntry,
    build_agent_server,
    encode_credential,
    register_all,
)
from memory_fabric.service import MemoryService
from memory_fabric.stage_trace import STAGES, StageTrace, StageTraceRecorder


class StageTraceContracts(unittest.TestCase):
    def test_validation_rejects_missing_unbalanced_and_negative_stage_rows(self) -> None:
        self.assertTrue(StageTrace("r", "x", {"auth": 2}, 2).validate())
        self.assertFalse(StageTrace("r", "x", {s: 1 for s in STAGES}, 2).validate())
        invalid = {s: 0 for s in STAGES}
        invalid["auth"] = -1
        self.assertTrue(StageTrace("r", "x", invalid, 0).validate())

    def test_api_stages_append_projection_and_copy_lookup(self) -> None:
        fabric = MemoryFabric(auto_activate=True, hold_suspicious=False)
        self.addCleanup(fabric.close)
        service = MemoryService(fabric=fabric)
        recorder = StageTraceRecorder()
        api = AgentApi(service, trace_recorder=recorder)
        register_all(service, [AgentEntry("writer", "tn_default", b"k" * 32)])
        credential = encode_credential(service.issue("writer", ttl_seconds=600))
        api.handle("remember", credential, {"content": "Pump P-4 is upstream."})

        trace, = recorder.snapshot()
        self.assertFalse(trace.validate(), trace.validate())
        self.assertGreater(trace.stages_ns["event_append"], 0)
        self.assertGreater(trace.stages_ns["projection"], 0)
        self.assertGreater(trace.stages_ns["copy_lookup"], 0)

    def test_http_request_has_balanced_decode_auth_serialization_transport(self) -> None:
        fabric = MemoryFabric(auto_activate=True, hold_suspicious=False)
        self.addCleanup(fabric.close)
        service = MemoryService(fabric=fabric)
        register_all(service, [AgentEntry("writer", "tn_default", b"k" * 32)])
        recorder = StageTraceRecorder()
        api = AgentApi(service, trace_recorder=recorder)
        server = build_agent_server(api, port=0)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        credential = encode_credential(service.issue("writer", ttl_seconds=600))
        request = urllib.request.Request(
            f"http://127.0.0.1:{server.server_address[1]}/v1/remember",
            data=json.dumps({"content": "Valve V-2 is upstream."}).encode(),
            headers={"Authorization": f"Bearer {credential}",
                     "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            self.assertEqual(response.status, 200)
            json.loads(response.read())
        traces = recorder.snapshot()
        http_trace = traces[-1]
        self.assertFalse(http_trace.validate(), http_trace.validate())
        for stage in ("body_decode", "auth", "event_append", "projection",
                      "copy_lookup", "serialization", "transport"):
            self.assertGreater(http_trace.stages_ns[stage], 0, stage)


if __name__ == "__main__":
    unittest.main()

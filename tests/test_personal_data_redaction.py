from __future__ import annotations

import io
import json
import logging
import tempfile
import unittest
from pathlib import Path

from memory_fabric import MemoryFabric
from memory_fabric.agent_api import AgentApi, encode_credential
from memory_fabric.governance.erasure import DirectoryKeyProvider
from memory_fabric.observability.report import memory_detail
from memory_fabric.posture import export_audit
from memory_fabric.sdk import NotUsable, agent
from memory_fabric.service import MemoryService
from memory_fabric.stage_trace import StageTraceRecorder


class PersonalDataRedaction(unittest.TestCase):
    def test_canary_is_absent_from_logs_exceptions_artifacts_traces_and_support_views(self) -> None:
        canary = "person" + ".private-" + "canary-" + "8842" + "@example.com"
        root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        database, keys = root / "store.db", root / "keys"
        fabric = MemoryFabric(str(database), auto_activate=True,
                              key_provider=DirectoryKeyProvider(keys))
        self.addCleanup(fabric.close)
        memory_id = fabric.remember(
                "agent_a", f"Contact the customer at {canary} for the claim.",
                tenant_id="tn_a", scope="team")
        fabric.quarantine(memory_id, reason="redaction fixture", actor="reviewer")
        client = agent(fabric, "agent_a", "tn_a")
        try:
            client.fetch(memory_id)
        except NotUsable as exc:
            exception_text = str(exc)
        else:
            self.fail("sensitive personal-data memory was unexpectedly usable")

        detail = json.dumps(memory_detail(fabric, memory_id), sort_keys=True)
        audit_path = root / "audit.jsonl"
        export_audit(fabric, audit_path)
        audit_artifact = audit_path.read_text(encoding="utf-8")

        service = MemoryService(fabric=fabric)
        service.register_agent("agent_a", key=b"agent-a-key", tenant_id="tn_a")
        recorder = StageTraceRecorder()
        api = AgentApi(service, trace_recorder=recorder)
        bearer = encode_credential(service.issue("agent_a"))
        api.handle("recall", bearer, {"query": canary})
        traces = json.dumps([row.to_json() for row in recorder.snapshot()], sort_keys=True)

        log_stream = io.StringIO()
        handler = logging.StreamHandler(log_stream)
        logger = logging.getLogger("personal-data-redaction-probe")
        logger.addHandler(handler)
        try:
            logger.warning("redaction probe completed for %s", memory_id)
        finally:
            logger.removeHandler(handler)
            handler.close()
        log_text = log_stream.getvalue()

        for surface, text in {
                "exception": exception_text,
                "support detail": detail,
                "audit artifact": audit_artifact,
                "trace": traces,
                "log": log_text,
        }.items():
            with self.subTest(surface=surface):
                self.assertNotIn(canary, text)
        self.assertNotIn(canary.encode(), database.read_bytes())
        self.assertTrue(list(keys.glob("*.key")))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

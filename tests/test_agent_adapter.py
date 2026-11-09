from __future__ import annotations

import socket
import http.client
import urllib.request
import unittest
from unittest.mock import patch

from benchmarks.agent_adapter import (
    AgentResponse,
    ScriptedPolicyAdapter,
    TaskEnvelope,
    run_adapter,
)


class OfflineAdapterContract(unittest.TestCase):
    def test_scripted_adapter_implements_transport_neutral_action_contract(self) -> None:
        tasks = [
            TaskEnvelope("supported", "publish", "record-1", ("status=1",), True),
            TaskEnvelope("missing", "publish", "record-2", (), False),
            TaskEnvelope("conflict", "publish", "record-3", ("status=1",), True, True),
        ]
        with (patch.object(socket, "create_connection", side_effect=AssertionError("network used")),
              patch.object(http.client.HTTPConnection, "connect", side_effect=AssertionError("HTTP used")),
              patch.object(urllib.request, "urlopen", side_effect=AssertionError("URL request used"))):
            responses = run_adapter(ScriptedPolicyAdapter(), tasks)
        self.assertEqual([r.decision for r in responses], ["act", "abstain", "abstain"])
        self.assertEqual(responses[0], AgentResponse("act", "publish", "record-1",
                                                     "status=1", "usable_evidence"))

    def test_adapter_response_cannot_change_the_task_request(self) -> None:
        task = TaskEnvelope("id", "publish", "target", ("safe",), True)
        response = run_adapter(ScriptedPolicyAdapter(), [task])[0]
        self.assertEqual((response.tool, response.target), (task.tool, task.target))


if __name__ == "__main__":
    unittest.main()

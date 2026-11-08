from __future__ import annotations

import statistics
import time
import unittest

from memory_fabric import MemoryFabric
from memory_fabric.agent_api import AgentApi, _ApiError, encode_credential
from memory_fabric.navigation import topics
from memory_fabric.sdk import NotUsable, agent
from memory_fabric.service import MemoryService


SECRET = "SAPPHIRE-CANARY-7419 acquisition timetable"
TENANT_B = "Tenant B unrelated maintenance notes"
MISSING = "01NOTAREALMEMORYID00000000"


def make_world(with_foreign_secret: bool):
    fabric = MemoryFabric(":memory:", auto_activate=True, seed=9)
    foreign = (fabric.remember("agent_a", SECRET, tenant_id="tn_a", scope="team")
               if with_foreign_secret else MISSING)
    view = agent(fabric, "agent_b", "tn_b")
    view.remember(TENANT_B, context={"topic": "maintenance"})
    return fabric, view, foreign


class MetadataSideChannels(unittest.TestCase):
    def test_counts_suggestions_http_errors_and_exceptions_match_empty_world(self) -> None:
        observations = []
        for with_secret in (False, True):
            fabric, client, foreign = make_world(with_secret)
            self.addCleanup(fabric.close)
            recalled = client.recall("SAPPHIRE-CANARY-7419 acquisition timetable")
            suggestion = topics(fabric, "agent_b", tenant_id="tn_b")
            try:
                client.fetch(foreign)
            except NotUsable as exc:
                sdk_error = (type(exc).__name__, exc.decision.reason_code,
                             exc.decision.version, exc.decision.detail)
            service = MemoryService(fabric=fabric)
            service.register_agent("agent_b", key=b"tenant-b-key", tenant_id="tn_b")
            bearer = encode_credential(service.issue("agent_b"))
            api = AgentApi(service)
            try:
                api.handle("fetch", bearer, {"memory_id": foreign})
            except _ApiError as exc:
                http_error = (exc.status.value, exc.message.replace(foreign, "<id>"))
            observations.append({
                "retrieval_count": len(recalled),
                "answerability": recalled.answerability.to_json(),
                "suggestions": suggestion,
                "sdk_error": sdk_error,
                "http_error": http_error,
            })

        self.assertEqual(observations[0], observations[1])
        self.assertNotIn("SAPPHIRE", str(observations[1]))

    def test_foreign_and_missing_fetch_have_the_same_coarse_timing_class(self) -> None:
        fabric, client, foreign = make_world(True)
        self.addCleanup(fabric.close)
        samples: dict[str, list[int]] = {"foreign": [], "missing": []}
        # Alternate probes to reduce drift from warm caches and scheduler load.
        for index in range(301):
            targets = [("foreign", foreign), ("missing", MISSING)]
            if index % 2:
                targets.reverse()
            for label, memory_id in targets:
                started = time.perf_counter_ns()
                try:
                    client.fetch(memory_id)
                except NotUsable:
                    pass
                samples[label].append(time.perf_counter_ns() - started)
        medians = {key: statistics.median(values) for key, values in samples.items()}
        # A 10x threshold only catches a distinct timing path; this is not a
        # proof of constant-time behavior or a production latency SLO.
        ratio = max(medians.values()) / max(1, min(medians.values()))
        self.assertLess(ratio, 10.0, medians)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

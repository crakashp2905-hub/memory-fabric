"""The authenticated agent API, over a real socket.

As with the SDK and the MCP server, most of these are about what a caller
cannot do: act without a valid credential, act as another agent, cross a
tenant, reach a withdrawn memory, or tell one kind of auth failure from another.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

from memory_fabric import MemoryFabric
from memory_fabric.agent_api import (
    AgentApi, ConfigurationError, build_agent_server, check_bind,
    _disagreements, decode_credential, encode_credential, load_agents, register_all,
)
from memory_fabric.service import MemoryService
from memory_fabric.sdk import agent, operator
from memory_fabric.identity import IdentityError

KEY_A = "aa" * 32
KEY_B = "bb" * 32
KEY_C = "cc" * 32


class ApiCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.agents_file = os.path.join(self.tmp.name, "agents")
        with open(self.agents_file, "w") as fh:
            fh.write(f"# agents\nag_a:tn_acme:{KEY_A}\nag_b:tn_acme:{KEY_B}\n"
                     f"ag_other:tn_globex:{KEY_C}\n")
        self.fabric = MemoryFabric(":memory:")
        writer = agent(self.fabric, "ag_seed", "tn_acme")
        self.mid = writer.remember("E01 at coastal sites: swap the pilot cable.")
        operator(self.fabric, "op").validate(self.mid)
        # An agent's write is private to it until shared; the other agents here
        # read it, so the operator shares it to the team.
        operator(self.fabric, "op").share(self.mid, "team")
        self.service = MemoryService(fabric=self.fabric)
        register_all(self.service, load_agents(self.agents_file))
        self.server = build_agent_server(AgentApi(self.service), port=0)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.fabric.close)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def token(self, agent_id: str = "ag_a", ttl: int = 600) -> str:
        return encode_credential(self.service.issue(agent_id, ttl_seconds=ttl))

    def post(self, op: str, body: dict, token: str | None = None,
             headers: dict | None = None) -> tuple[int, dict]:
        h = {"Content-Type": "application/json", **(headers or {})}
        if token:
            h["Authorization"] = f"Bearer {token}"
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/v1/{op}",
                                     data=json.dumps(body).encode(), headers=h,
                                     method="POST")
        try:
            with urllib.request.urlopen(req, timeout=10) as res:
                return res.status, json.loads(res.read())
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read() or b"{}")


class TestTheSurface(ApiCase):
    def test_http_behavior_characterization_snapshot(self) -> None:
        expected = json.loads((Path(__file__).parent / "data/agent_api_behavior.json")
                              .read_text(encoding="utf-8"))
        token = self.token()
        recall_status, recall = self.post("recall", {"query": "pilot cable coastal"}, token)
        memory = next(row for row in recall["memories"] if row["memory_id"] == self.mid)
        observed = {
            "unauthenticated": {"status": self.post("recall", {"query": "pilot"})[0],
                                "body": self.post("recall", {"query": "pilot"})[1]},
            "invalid_recall_limit": {"status": self.post(
                "recall", {"query": "pilot", "k": 0}, token)[0],
                "body": self.post("recall", {"query": "pilot", "k": 0}, token)[1]},
            "unknown_operation": {"status": self.post("record_outcome", {}, token)[0],
                                  "body": self.post("record_outcome", {}, token)[1]},
            "recall": {"status": recall_status,
                       "top_level_keys": sorted(recall),
                       "memory_keys": sorted(memory),
                       "memory_content": memory["content"],
                       "answerability_keys": sorted(recall["answerability"]),
                       "disagreements_type": type(recall["disagreements"]).__name__},
        }
        self.assertEqual(observed, expected)

    def test_benchmark_profile_is_local_opt_in_and_resettable(self) -> None:
        import tracemalloc

        was_tracing = tracemalloc.is_tracing()
        profile_token = "profile-token-for-test-only-1234567890"
        api = AgentApi(self.service)
        with patch.dict(os.environ, {"MEMORY_FABRIC_PROFILE": "1",
                                    "MEMORY_FABRIC_PROFILE_ALLOCATIONS": "1",
                                    "MEMORY_FABRIC_PROFILE_TOKEN": profile_token}):
            server = build_agent_server(api, port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{server.server_address[1]}"
            denied = urllib.request.Request(base + "/__profile/reset")
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(denied, timeout=2)
            self.assertEqual(caught.exception.code, 404)
            profile_headers = {"X-Memory-Fabric-Profile-Token": profile_token}
            authorized = urllib.request.Request(base + "/__profile/reset",
                                                headers=profile_headers)
            with urllib.request.urlopen(authorized, timeout=2) as response:
                self.assertEqual(response.status, 200)
            credential = self.token()
            request = urllib.request.Request(
                base + "/v1/recall", data=json.dumps({"query": "pilot cable"}).encode(),
                headers={"Authorization": f"Bearer {credential}",
                         "Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(request, timeout=2) as response:
                self.assertEqual(response.status, 200)
            request = urllib.request.Request(base + "/__profile", headers=profile_headers)
            with urllib.request.urlopen(request, timeout=2) as response:
                profile = json.loads(response.read())
            self.assertIn("server_python_allocation_peak_bytes", profile)
            self.assertIn("fabric_lock_wait", profile)

            credential = self.token()
            waiting = threading.Event()
            errors: list[BaseException] = []

            def blocked_recall() -> None:
                waiting.set()
                try:
                    api.handle("recall", credential, {"query": "pilot cable"},
                               remote="127.0.0.1")
                except BaseException as exc:  # surfaced in the test thread
                    errors.append(exc)

            with self.fabric.lock:
                worker = threading.Thread(target=blocked_recall)
                worker.start()
                self.assertTrue(waiting.wait(2))
                time.sleep(0.05)
            worker.join(timeout=5)
            self.assertFalse(worker.is_alive())
            self.assertEqual(errors, [])
            measured = api.profile_recorder.snapshot()["fabric_lock_wait"]
            self.assertGreaterEqual(measured["total"], 20_000_000)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
            if not was_tracing:
                tracemalloc.stop()

    def test_recall_verify_remember(self) -> None:
        token = self.token()
        status, body = self.post("recall", {"query": "pilot cable coastal"}, token)
        self.assertEqual(status, 200)
        self.assertIn(self.mid, [m["memory_id"] for m in body["memories"]])
        status, body = self.post("verify", {"memory_id": self.mid}, token)
        self.assertEqual((status, body["usable"]), (200, True))
        status, body = self.post("remember", {"content": "Reset the breaker first."}, token)
        self.assertEqual((status, body["state"]), (200, "candidate"))
        self.assertEqual(self.fabric.get(body["memory_id"]).provenance.created_by, "ag_a")

    def test_a_retraction_reaches_the_next_verify(self) -> None:
        token = self.token()
        self.post("recall", {"query": "pilot cable coastal"}, token)
        operator(self.fabric, "op").retract(self.mid, reason="wrong", basis="contradicted")
        status, body = self.post("verify", {"memory_id": self.mid}, token)
        self.assertEqual((status, body["usable"]), (200, False))
        from memory_fabric.sdk import NotUsable, agent
        with self.assertRaises(NotUsable) as expected:
            agent(self.fabric, "ag_a", "tn_acme").fetch(self.mid)
        status, body = self.post("fetch", {"memory_id": self.mid}, token)
        self.assertEqual(status, 403)
        self.assertIn(expected.exception.decision.reason_code, body["error"])

    def test_there_is_no_outcome_endpoint(self) -> None:
        status, body = self.post("record_outcome", {"episode_id": "x", "outcome": 1.0},
                                 self.token())
        self.assertEqual(status, 404)
        self.assertEqual(body["error"], "unknown operation")

    def test_recall_always_has_structured_disagreements(self) -> None:
        status, body = self.post("recall", {"query": "pilot cable coastal"}, self.token())
        self.assertEqual(status, 200)
        self.assertEqual(body["disagreements"], [])


class TestContradictionRendering(unittest.TestCase):
    def test_names_alternatives_sources_and_support(self) -> None:
        fabric = MemoryFabric(":memory:", auto_activate=True, hold_suspicious=False)
        self.addCleanup(fabric.close)
        left = fabric.remember("ag_a", "Pump P-14 pressure is 12 bar.", scope="team")
        right = fabric.remember("ag_b", "Pump P-14 pressure is 9 bar.", scope="team")
        rendered = _disagreements(
            fabric, [fabric.state.memories[left], fabric.state.memories[right]])
        self.assertEqual(len(rendered), 1)
        self.assertEqual(rendered[0]["status"], "unresolved")
        self.assertEqual({a["source"] for a in rendered[0]["alternatives"]},
                         {"ag_a", "ag_b"})
        self.assertTrue(all(a["independent_sources"] >= 1
                            for a in rendered[0]["alternatives"]))


class TestIdentityAndTenancy(ApiCase):
    def test_no_credential_is_refused(self) -> None:
        self.assertEqual(self.post("recall", {"query": "pilot"})[0], 401)

    def test_every_auth_failure_looks_the_same(self) -> None:
        good = self.service.issue("ag_a", ttl_seconds=600)
        from dataclasses import replace
        forged = encode_credential(replace(good, agent_id="ag_b"))
        # Correctly signed, only the expiry wrong: the registry will not issue
        # one, so it is built and signed here with the agent's own key.
        expired = encode_credential(
            replace(good, expires_at=good.issued_at - 1).sign(bytes.fromhex(KEY_A)))
        revoked_cred = self.service.issue("ag_a", ttl_seconds=600)
        self.service.revoke(revoked_cred)
        bodies = []
        for token in (forged, expired, encode_credential(revoked_cred), "garbage!!"):
            status, body = self.post("recall", {"query": "pilot"}, token)
            self.assertEqual(status, 401)
            bodies.append(body)
        self.assertEqual(len({json.dumps(b) for b in bodies}), 1)

    def test_another_tenant_cannot_see_it(self) -> None:
        status, body = self.post("recall", {"query": "pilot cable coastal"},
                                 self.token("ag_other"))
        self.assertEqual(status, 200)
        self.assertEqual(body["memories"], [])
        self.assertEqual(self.post("fetch", {"memory_id": self.mid},
                                   self.token("ag_other"))[0], 403)

    def test_tokens_are_per_agent(self) -> None:
        """ag_b cannot verify on the strength of ag_a's recall.

        ag_b's verify fetches the memory under ag_b's own permission check and
        token (so a withdrawn memory can be answered as withdrawn); ag_a's token
        is never used for it.
        """
        self.post("recall", {"query": "pilot cable coastal"}, self.token("ag_a"))
        status, body = self.post("verify", {"memory_id": self.mid}, self.token("ag_b"))
        self.assertEqual(status, 200, body)
        self.assertTrue(body["usable"])


class TestTransportDefences(ApiCase):
    def test_browser_requests_are_refused(self) -> None:
        status, _ = self.post("recall", {"query": "pilot"}, self.token(),
                              headers={"Origin": "https://evil.example"})
        self.assertEqual(status, 403)

    def test_oversized_bodies_are_refused(self) -> None:
        status, _ = self.post("remember", {"content": "x" * 70_000}, self.token())
        self.assertEqual(status, 413)

    def test_plain_http_off_loopback_is_refused(self) -> None:
        with self.assertRaises(ConfigurationError):
            check_bind("0.0.0.0", behind_tls=False)
        check_bind("0.0.0.0", behind_tls=True)

    def test_credential_round_trip(self) -> None:
        credential = self.service.issue("ag_a", ttl_seconds=60)
        self.assertEqual(decode_credential(encode_credential(credential)), credential)

    def test_credential_decode_errors_are_refused_cleanly(self) -> None:
        for token in ("%%%", "e30", "eyJ4Ijoi" + "A" * 2048):
            with self.subTest(token=token[:12]), self.assertRaises(IdentityError):
                decode_credential(token)


class TestAgentsFile(unittest.TestCase):
    def test_refuses_weak_or_malformed_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "agents")
            for name, text in {
                "short key": "ag:tn:abcd",
                "not hex": "ag:tn:" + "zz" * 32,
                "missing field": "ag:" + "aa" * 32,
                "duplicate": f"ag:tn:{KEY_A}\nag:tn:{KEY_B}",
                "empty": "# none",
            }.items():
                with self.subTest(name):
                    with open(path, "w") as fh:
                        fh.write(text)
                    with self.assertRaises(ConfigurationError):
                        load_agents(path)


class TestCli(unittest.TestCase):
    def test_issue_prints_a_credential_the_server_accepts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = os.path.join(tmp, "s.db")
            agents = os.path.join(tmp, "agents")
            with open(agents, "w") as fh:
                fh.write(f"ag_a:tn_default:{KEY_A}\n")
            done = subprocess.run(
                [sys.executable, "-m", "memory_fabric", "--db", db, "--create",
                 "agent-api-issue", "--agents-file", agents, "--agent", "ag_a"],
                capture_output=True, text=True, timeout=60)
            self.assertEqual(done.returncode, 0, done.stderr)
            credential = decode_credential(done.stdout.strip())
            self.assertEqual(credential.agent_id, "ag_a")


if __name__ == "__main__":
    unittest.main()

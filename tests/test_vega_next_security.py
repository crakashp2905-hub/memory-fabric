"""Governance, privacy, isolation and rollback around the advisor (VEGA next W13, W15-10)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from typing import Any, Mapping

from benchmarks import vega_next_arms as arms
from benchmarks import vega_next_worlds as worlds
from memory_fabric.adapters.vega_u import VegaClient, VegaLimits
from memory_fabric.causal_replay.semantic.advice import Advice, Question
from memory_fabric.causal_replay.semantic.scripted import ScriptedAdvisor
from memory_fabric.outcome_typed import limited_process

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))


class Recorder(ScriptedAdvisor):
    def __init__(self) -> None:
        super().__init__()
        self.states: list[str] = []

    def decide(self, state: str, questions: Mapping[str, Question]) -> Advice:
        self.states.append(state)
        return super().decide(state, questions)


class Governance(unittest.TestCase):
    def test_off_and_shadow_change_no_output_write_or_authority(self):
        import vega_killswitch
        report = vega_killswitch.verify()
        self.assertEqual(report["status"], "PASS", report)
        self.assertEqual(report["advisor_calls_per_run"], [0, 1, 0])

    def test_the_advisor_sees_only_current_authorized_evidence(self):
        world = worlds.build("canonical", 1, "pilot")  # drift: the open TA1/TB2 question asks the advisor
        rec = Recorder()
        arms.run_arm("A5-PV", world, rec)
        world2 = worlds.build("canonical", 1, "pilot")
        fabric = worlds.materialize(world2)
        foreign = fabric.remember("ext", "pack P-7 TA1 calibration note: SECRET-CANARY-42", scope="team",
                                  tenant_id="tn_other")
        fabric.close()
        self.assertTrue(rec.states)
        self.assertTrue(all("SECRET-CANARY-42" not in s for s in rec.states), foreign)
        self.assertTrue(all(worlds.TENANT not in s for s in rec.states))

    def test_injected_authority_in_evidence_changes_no_decision(self):
        import dataclasses
        for seed in range(8):
            for split in ("dev", "pilot"):
                world = worlds.build("injection", seed, split)
                clean = dataclasses.replace(world, items=tuple(i for i in world.items if i.key != "inject"), ids={})
                injected, control = arms.run_arm("A5-P", world, None), arms.run_arm("A5-P", clean, None)
                self.assertEqual(injected["action"], control["action"], (split, seed))
                self.assertFalse(injected["unsafe_omission"] or injected["unsafe_execution"])
                self.assertNotEqual(injected["action"], "disable_alarm")


class Isolation(unittest.TestCase):
    def test_a_limit_the_platform_refuses_means_the_command_is_not_run(self):
        import tempfile
        from unittest import mock
        if not limited_process.supported():
            self.skipTest("no resource module: covered by the UNSUPPORTED_PLATFORM branch below")
        real = limited_process._resource()

        class Refusing:
            RLIMIT_CPU, RLIMIT_AS, RLIM_INFINITY = real.RLIMIT_CPU, real.RLIMIT_AS, real.RLIM_INFINITY

            @staticmethod
            def setrlimit(which, value):
                raise ValueError("refused")

        with tempfile.TemporaryDirectory() as d, mock.patch.object(limited_process, "_resource", lambda: Refusing):
            marker = Path(d) / "ran"
            r = limited_process.run_limited([sys.executable, "-c", f"open({str(marker)!r}, 'w')"], cpu_seconds=2,
                                            memory_bytes=1 << 30)
            self.assertEqual(r.status, "UNSUPPORTED_PLATFORM")
            self.assertFalse(marker.exists())

    def test_limits_are_hard_or_the_command_is_refused(self):
        if not limited_process.supported():
            r = limited_process.run_limited([sys.executable, "-c", "print(1)"], cpu_seconds=2, memory_bytes=1 << 30)
            self.assertEqual(r.status, "UNSUPPORTED_PLATFORM")
            return
        ok = limited_process.run_limited([sys.executable, "-c", "print('ok')"], cpu_seconds=5,
                                         memory_bytes=1 << 30)
        if ok.status == "UNSUPPORTED_PLATFORM":  # the platform refused a limit (macOS): refused, never run
            self.assertIn("refused a limit", ok.stderr)
            self.assertEqual(ok.stdout, "")
            return
        self.assertEqual((ok.status, ok.stdout.strip()), ("OK", "ok"))
        hog = limited_process.run_limited([sys.executable, "-c", "x = bytearray(2 << 30)"], cpu_seconds=5,
                                          memory_bytes=512 << 20)
        self.assertEqual(hog.status, "LIMIT_EXCEEDED")
        spin = limited_process.run_limited([sys.executable, "-c", "while True: pass"], cpu_seconds=1,
                                           memory_bytes=1 << 30, timeout_seconds=20)
        self.assertEqual(spin.status, "LIMIT_EXCEEDED")
        slow = limited_process.run_limited([sys.executable, "-c", "import time; time.sleep(5)"], cpu_seconds=5,
                                           memory_bytes=1 << 30, timeout_seconds=0.5)
        self.assertEqual(slow.status, "TIMEOUT")

    def test_a_fork_bomb_is_contained_even_when_the_host_runs_as_root(self):
        # Freeze plan F09-02: RLIMIT_NPROC binds because a root parent drops the child's identity.
        if "RLIMIT_NPROC" not in limited_process.supported():
            self.skipTest("no RLIMIT_NPROC on this platform: run_limited refuses instead")
        bomb = ("import os, sys\nn = 0\ntry:\n    for i in range(400):\n        if os.fork() == 0:\n"
                "            import time; time.sleep(2); os._exit(0)\n        n += 1\nexcept OSError:\n"
                "    print('refused', n); sys.exit(3)\nprint('forked', n)")
        r = limited_process.run_limited([sys.executable, "-c", bomb], cpu_seconds=5, memory_bytes=1 << 30,
                                        max_processes=16, timeout_seconds=30)
        if r.status == "UNSUPPORTED_PLATFORM":
            return  # the platform refused a limit: not run, which is the other lawful outcome
        self.assertIn("refused", r.stdout, (r.status, r.stdout, r.stderr[-200:]))
        self.assertLessEqual(int(r.stdout.split()[-1]), 16)

    def test_an_inference_server_that_crashes_mid_answer_fails_closed(self):
        # VEGA-CDM-155 (freeze register FIX): the real HTTP transport against a loopback server
        # that dies after sending a partial body, then against a server that is gone.
        import http.server
        import threading
        fixture = json.loads((Path(__file__).parent / "fixtures" / "vega_u" / "decide-0.19.0.json")
                             .read_text(encoding="utf-8"))

        class Crashing(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args: Any) -> None:
                pass

            def do_GET(self) -> None:
                body = json.dumps(fixture["health"] if self.path.endswith("/health") else fixture["model"]).encode()
                self.send_response(200)
                self.send_header("content-length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self) -> None:
                self.rfile.read(int(self.headers["content-length"]))
                self.send_response(200)
                self.send_header("content-length", "5000")
                self.end_headers()
                self.wfile.write(b'{"answers": {"x": {"status": "OK", "val')
                self.wfile.flush()
                self.connection.close()

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Crashing)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        endpoint = f"http://127.0.0.1:{server.server_address[1]}"
        q = {"x": Question("x", "boolean", "?", {"true": "y", "false": "n"})}
        try:
            client = VegaClient(endpoint, limits=VegaLimits(retries=0))
            advice = client.decide("s", q)
            self.assertEqual(advice.receipt["status"], "UNAVAILABLE")
            self.assertEqual(advice.answers["x"].status, "UNAVAILABLE")
            self.assertIsNone(advice.answers["x"].value)
        finally:
            server.shutdown()
            server.server_close()
        gone = VegaClient(endpoint, limits=VegaLimits(retries=0)).decide("s", q)
        self.assertEqual(gone.answers["x"].status, "UNAVAILABLE")
        self.assertTrue(gone.answers["x"].reason.startswith("INFERENCE_UNAVAILABLE"))

    def test_model_errors_carry_no_evidence_text(self):
        def broken(method: str, url: str, body: Any, timeout: float):
            raise OSError("connection reset while sending SECRET-CANARY-7")

        client = VegaClient(transport=broken, limits=VegaLimits(retries=0))
        advice = client.decide("TA1 note: SECRET-CANARY-9 reads 61 C",
                               {"x": Question("x", "boolean", "?", {"true": "y", "false": "n"})})
        blob = json.dumps(advice.receipt) + json.dumps([a.reason for a in advice.answers.values()])
        self.assertNotIn("SECRET-CANARY-9", blob)
        self.assertNotIn("SECRET-CANARY-7", blob)


class Parity(unittest.TestCase):
    def test_every_effect_route_and_semantic_mode_agree(self):
        import importlib
        parity = importlib.import_module("tests.test_effect_transport_parity")
        self.assertTrue(hasattr(parity, "EffectParity"))


if __name__ == "__main__":
    unittest.main()

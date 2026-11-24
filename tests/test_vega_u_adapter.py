"""The vega-U loopback client against a recorded real response (VEGA S01).

The fixture was recorded from vegaml 0.19.0 serving the 0.8B reader on CPU; these
tests replay it through a fake transport, so they need no model, torch or network.
A real-server test runs only when ``MEMORY_FABRIC_VEGA_URL`` is set.
"""

from __future__ import annotations

import copy
import json
import math
import os
import unittest
from pathlib import Path

from memory_fabric.adapters.vega_u import (RECORDED_ENGINE_SHA256, VegaClient, VegaConfigError,
                                           VegaLimits, VegaPins, check_endpoint)
from memory_fabric.causal_replay.semantic.advice import Question, parse_decision

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "vega_u" / "decide-0.19.0.json")
                     .read_text(encoding="utf-8"))


def questions() -> dict[str, Question]:
    out = {}
    for name, q in FIXTURE["request"]["questions"].items():
        criteria = tuple(q["criteria"]) if q["type"] == "score" else q["criteria"]
        out[name] = Question(name, q["type"], q["instructions"], criteria)
    return out


class FakeServer:
    def __init__(self, response=None, model=None, health=None, status=200):
        self.response = response if response is not None else FIXTURE["response"]
        self.model = model if model is not None else FIXTURE["model"]
        self.health = health if health is not None else FIXTURE["health"]
        self.status = status
        self.calls: list[tuple[str, str, bytes | None]] = []

    def __call__(self, method, url, body, timeout):
        self.calls.append((method, url, body))
        if url.endswith("/health"):
            return 200, json.dumps(self.health).encode()
        if url.endswith("/v1/model"):
            return 200, json.dumps(self.model).encode()
        if isinstance(self.status, Exception):
            raise self.status
        return self.status, json.dumps(self.response).encode()


class Protocol(unittest.TestCase):
    def test_the_request_is_v1_decide_with_boolean_not_the_legacy_shape(self):
        server = FakeServer()
        client = VegaClient(transport=server)
        advice = client.decide(FIXTURE["request"]["state"], questions())
        method, url, body = server.calls[-1]
        self.assertEqual((method, url), ("POST", "http://127.0.0.1:8011/v1/decide"))
        sent = json.loads(body)
        self.assertEqual(sent, FIXTURE["request"])
        self.assertNotIn("systemone", url)
        self.assertNotIn("noul", body.decode())
        self.assertEqual(advice.receipt["evidence_level"], "VEGA_MODEL_SMOKE")

    def test_the_recorded_answers_parse_without_filling_anything(self):
        answers = parse_decision(questions(), FIXTURE["response"])
        support, cause, urgency = (answers[k] for k in ("claim_support", "causal_candidate", "urgency"))
        self.assertEqual((support.status, support.value), ("OK", "unknown"))
        self.assertEqual(cause.prediction_set, ("false",))
        self.assertAlmostEqual(cause.probs["true"], cause.value)
        self.assertEqual(urgency.status, "ABSTAIN")
        self.assertEqual(urgency.prediction_set, ("1", "2"))
        self.assertFalse(urgency.decisive)

    def test_receipts_carry_digests_pins_and_what_the_server_reported(self):
        advice = VegaClient(transport=FakeServer()).decide("state", questions())
        receipt = advice.receipt
        for key in ("request_digest", "response_digest", "receipt_digest", "latency_s"):
            self.assertTrue(receipt[key] is not None)
        self.assertEqual(receipt["reported"]["engine_sha256"], RECORDED_ENGINE_SHA256)
        self.assertEqual(receipt["pins"]["reader"], "Qwen3.5-0.8B")


class FailClosed(unittest.TestCase):
    def test_only_loopback_http_endpoints_are_accepted(self):
        for bad in ("http://10.0.0.5:8011", "https://127.0.0.1:8011", "http://example.com",
                    "http://127.0.0.1:8011/v1/decide", "http://user@127.0.0.1:8011"):
            with self.subTest(endpoint=bad), self.assertRaises(VegaConfigError):
                check_endpoint(bad)
        self.assertEqual(check_endpoint("http://localhost:9000/"), "http://localhost:9000")

    def test_an_unregistered_reader_or_substituted_checkpoint_is_refused(self):
        with self.assertRaises(VegaConfigError):
            VegaPins(reader="Qwen3.8-27B")
        swapped = copy.deepcopy(FIXTURE["model"])
        swapped["audit"]["engine_sha256"] = "0" * 64
        advice = VegaClient(transport=FakeServer(model=swapped)).decide("s", questions())
        self.assertTrue(all(a.status == "UNAVAILABLE" for a in advice.answers.values()))
        self.assertIn("engine_sha256", next(iter(advice.answers.values())).reason)
        self.assertEqual(advice.receipt["evidence_level"], "MODEL_NOT_RUN")

    def test_missing_metadata_unloaded_model_and_fitted_heads_fail_the_handshake(self):
        cases = {"no audit": {"model": {k: v for k, v in FIXTURE["model"].items() if k != "audit"}},
                 "not loaded": {"health": {"status": "ok", "model_loaded": False}},
                 "heads": {"model": {**FIXTURE["model"], "heads_fitted": 2}}}
        for name, kwargs in cases.items():
            with self.subTest(case=name):
                advice = VegaClient(transport=FakeServer(**kwargs)).decide("s", questions())
                self.assertFalse(advice.available)

    def test_malformed_outputs_become_invalid_never_confident(self):
        def mutate(fn):
            response = copy.deepcopy(FIXTURE["response"])
            fn(response["answers"])
            return parse_decision(questions(), response)

        def bad_prob(a):
            a["claim_support"]["probs"]["supported"] = math.nan
        cases = {
            "nan": bad_prob,
            "unnormalised": lambda a: a["claim_support"]["probs"].update(unknown=0.99),
            "foreign choice": lambda a: a["claim_support"].update(choice="approve"),
            "bad set": lambda a: a["claim_support"].update(prediction_set=["approve"]),
            "missing abstain": lambda a: a["causal_candidate"].pop("abstain"),
            "boolean out of range": lambda a: a["causal_candidate"].update(boolean=1.7),
            "score off scale": lambda a: a["urgency"].update(score=9),
            "empty set": lambda a: a["urgency"].update(prediction_set=[]),
        }
        for name, fn in cases.items():
            with self.subTest(case=name):
                answers = mutate(fn)
                self.assertIn("INVALID", {x.status for x in answers.values()})
        extra = copy.deepcopy(FIXTURE["response"])
        extra["answers"]["grant_tool"] = {"choice": "yes"}
        self.assertTrue(all(x.status == "INVALID" for x in parse_decision(questions(), extra).values()))

    def test_timeouts_errors_and_budgets_fall_back_and_the_breaker_opens(self):
        now = [0.0]
        server = FakeServer(status=OSError("connection refused"))
        client = VegaClient(transport=server, clock=lambda: now[0],
                            limits=VegaLimits(retries=1, breaker_failures=2, breaker_cooldown_s=30))
        for _ in range(2):
            advice = client.decide("s", questions())
            self.assertTrue(all(a.status == "UNAVAILABLE" for a in advice.answers.values()))
        posts = sum(1 for c in server.calls if c[0] == "POST")
        self.assertEqual(posts, 4)  # one retry each, then the breaker
        advice = client.decide("s", questions())
        self.assertEqual(advice.receipt["status"], "CIRCUIT_OPEN")
        self.assertEqual(sum(1 for c in server.calls if c[0] == "POST"), posts)
        too_big = VegaClient(transport=FakeServer(), limits=VegaLimits(max_state_bytes=10))
        self.assertEqual(too_big.decide("x" * 11, questions()).receipt["status"], "OVER_BUDGET")
        refused = VegaClient(transport=FakeServer(status=422))
        refused.decide("s", questions())
        self.assertEqual(sum(1 for c in refused.transport.calls if c[0] == "POST"), 1)  # type: ignore[attr-defined]

    def test_the_core_package_imports_no_model_runtime(self):
        import memory_fabric.adapters.vega_u as module
        source = Path(module.__file__).read_text(encoding="utf-8")
        for name in ("torch", "vegaml", "transformers", "huggingface_hub", "requests", "httpx"):
            self.assertNotIn(f"import {name}", source)


@unittest.skipUnless(os.environ.get("MEMORY_FABRIC_VEGA_URL"), "no local vega-U server configured")
class RealServer(unittest.TestCase):
    """Real local inference. Never run by default; evidence level VEGA_MODEL_SMOKE."""

    def test_a_real_decision_round_trips_with_pinned_identity(self):
        client = VegaClient(os.environ["MEMORY_FABRIC_VEGA_URL"])
        advice = client.decide(FIXTURE["request"]["state"], questions())
        self.assertEqual(advice.receipt["evidence_level"], "VEGA_MODEL_SMOKE")
        self.assertTrue(all(a.status in ("OK", "ABSTAIN") for a in advice.answers.values()))


if __name__ == "__main__":
    unittest.main()

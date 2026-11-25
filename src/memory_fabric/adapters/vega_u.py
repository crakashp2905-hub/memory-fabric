"""A loopback client for vega-U's ``POST /v1/decide`` (VEGA S01).

Not the System One client (:mod:`.systemone`): that one speaks Kev/TypeSafe's
``POST /v1/systemone`` with ``noul`` questions, and vegaml speaks
``POST /v1/decide`` with ``boolean`` questions and a different response shape
(``answers.<name>.{choice|boolean|score, probs, prediction_set, abstain,
unbound, readout}``). The two are not silently coerced into each other; see
``docs/architecture/ADR-VEGA-CDM-001.md``.

What the client guarantees, all with the standard library only (vegaml, torch
and the weights live in a separate optional environment and are never
downloaded by this package):

* **Loopback only.** The endpoint must be ``127.0.0.1``, ``::1`` or
  ``localhost`` over plain HTTP, and requests bypass every proxy, so no
  configured ``HTTPS_PROXY`` can send evidence off the machine (VEGA-CDM-018).
* **Fail-closed handshake.** ``GET /health`` must say the model is loaded and
  ``GET /v1/model`` must report the pinned runtime version, reader and engine
  digest; a missing field or a mismatch refuses every later call (015-017).
* **Registered readers only.** ``Qwen3.5-0.8B`` and ``Qwen3.5-4B``; anything else
  is refused, including a server that silently loaded another (016).
* **Bounded.** A per-call deadline, a small retry budget for connection
  failures, limits on questions and state bytes, and a circuit breaker that
  stops calling after repeated failures (019).
* **Advisory output only.** :meth:`VegaClient.decide` returns
  :class:`~memory_fabric.causal_replay.semantic.advice.Advice`: typed answers and
  a receipt. It has no route to a store, a tool or a grant (011).

Every receipt carries the request and response digests, the reported and pinned
model identity, latency and the evidence level. A receipt is ``VEGA_MODEL_SMOKE``
only when the handshake matched the pinned engine digest; the client cannot
prove what process answered, so the digest is what the server *reported*.
"""

from __future__ import annotations

__stability__ = "experimental"

import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from ..causal_replay.semantic.advice import Advice, Question, parse_decision, unavailable

REGISTERED_READERS = frozenset({"Qwen3.5-0.8B", "Qwen3.5-4B"})
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})
DEFAULT_ENDPOINT = "http://127.0.0.1:8011"
RECORDED_ENGINE_SHA256 = "78f96be7c6a06abb873e573fcf9e43ef467010a30c72cd6cac32538cd7078db8"
"""The vega-U engine recorded in ``tests/fixtures/vega_u/decide-0.19.0.json``
(Hub revision ``6aee375845724d2cca21d5fd5c043a028dbc1b48``)."""


class VegaConfigError(ValueError):
    pass


@dataclass(frozen=True)
class VegaPins:
    runtime_version: str = "0.19.0"
    reader: str = "Qwen3.5-0.8B"
    engine_sha256: str = RECORDED_ENGINE_SHA256
    calibration_version: str | None = None

    def __post_init__(self) -> None:
        if self.reader not in REGISTERED_READERS:
            raise VegaConfigError(f"reader {self.reader!r} is not registered")
        if len(self.engine_sha256) != 64:
            raise VegaConfigError("engine_sha256 must be a SHA-256 hex digest")


@dataclass(frozen=True)
class VegaLimits:
    deadline_s: float = 60.0
    retries: int = 1
    max_questions: int = 8
    max_state_bytes: int = 32_000
    breaker_failures: int = 3
    breaker_cooldown_s: float = 30.0

    def __post_init__(self) -> None:
        if not 0 < self.deadline_s <= 600 or not 0 <= self.retries <= 3:
            raise VegaConfigError("deadline must be in (0, 600] s and retries in [0, 3]")
        if self.max_questions < 1 or self.max_state_bytes < 1 or self.breaker_failures < 1:
            raise VegaConfigError("limits must be positive")


def check_endpoint(endpoint: str) -> str:
    parsed = urllib.parse.urlsplit(endpoint)
    if parsed.scheme != "http" or parsed.hostname not in LOOPBACK_HOSTS:
        raise VegaConfigError("the vega-U endpoint must be plain HTTP on a loopback address")
    if parsed.path not in ("", "/") or parsed.query or parsed.fragment or parsed.username:
        raise VegaConfigError("the endpoint is a bare loopback origin")
    return f"http://{parsed.netloc}"


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


Transport = Callable[[str, str, bytes | None, float], tuple[int, bytes]]


def _urllib_transport(method: str, url: str, body: bytes | None, timeout: float) -> tuple[int, bytes]:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    request = urllib.request.Request(url, data=body, method=method,
                                     headers={"content-type": "application/json"})
    try:
        with opener.open(request, timeout=timeout) as response:
            return response.status, response.read(4_000_000)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(4_000_000)


@dataclass
class VegaClient:
    endpoint: str = DEFAULT_ENDPOINT
    pins: VegaPins = field(default_factory=VegaPins)
    limits: VegaLimits = field(default_factory=VegaLimits)
    transport: Transport = _urllib_transport
    clock: Callable[[], float] = time.monotonic
    _model: Mapping[str, Any] | None = None
    _handshake_error: str | None = None
    _failures: int = 0
    _open_until: float = 0.0

    def __post_init__(self) -> None:
        self.endpoint = check_endpoint(self.endpoint)

    # --- handshake -------------------------------------------------------

    def _get(self, path: str) -> Any:
        status, body = self.transport("GET", self.endpoint + path, None, min(10.0, self.limits.deadline_s))
        if status != 200:
            raise ConnectionError(f"{path} returned {status}")
        return json.loads(body)

    def handshake(self) -> Mapping[str, Any]:
        """Check health and pinned identity; remember a failure so every call refuses."""
        try:
            health = self._get("/health")
            if not isinstance(health, Mapping) or health.get("model_loaded") is not True:
                raise ValueError("the model is not loaded")
            model = self._get("/v1/model")
            audit = model.get("audit") if isinstance(model, Mapping) else None
            if not isinstance(audit, Mapping):
                raise ValueError("/v1/model has no audit block")
            reported = {"runtime_version": audit.get("vegaml"), "reader": audit.get("reader"),
                        "engine_sha256": audit.get("engine_sha256"),
                        "calibration_version": audit.get("calibration_version")}
            expected = {"runtime_version": self.pins.runtime_version, "reader": self.pins.reader,
                        "engine_sha256": self.pins.engine_sha256,
                        "calibration_version": self.pins.calibration_version}
            wrong = sorted(k for k in expected if reported[k] != expected[k])
            if wrong:
                raise ValueError(f"model identity differs from the pins: {wrong}")
            if model.get("heads_fitted"):
                raise ValueError("fitted heads are loaded; only the pinned engine readout is registered")
        except OSError as exc:
            # The message of a transport error can echo request or server text, so only the
            # type is kept (VEGA next W13-09).
            self._model, self._handshake_error = None, type(exc).__name__
            raise ConnectionError(self._handshake_error) from exc
        except (ValueError, json.JSONDecodeError) as exc:
            self._model, self._handshake_error = None, f"{type(exc).__name__}: {exc}"
            raise ConnectionError(self._handshake_error) from exc
        self._model, self._handshake_error = dict(reported), None
        return self._model

    # --- decisions -------------------------------------------------------

    def _receipt(self, **extra: Any) -> dict[str, Any]:
        receipt = {"adapter": "vega_u.v1", "endpoint": self.endpoint,
                   "pins": {"runtime_version": self.pins.runtime_version, "reader": self.pins.reader,
                            "engine_sha256": self.pins.engine_sha256,
                            "calibration_version": self.pins.calibration_version},
                   "reported": dict(self._model) if self._model else None,
                   "evidence_level": "VEGA_MODEL_SMOKE" if self._model else "MODEL_NOT_RUN", **extra}
        receipt["receipt_digest"] = _digest(receipt)
        return receipt

    def decide(self, state: str, questions: Mapping[str, Question]) -> Advice:
        if not questions or len(questions) > self.limits.max_questions:
            return unavailable(questions, "OVER_BUDGET: question count", self._receipt(status="OVER_BUDGET"))
        if len(state.encode("utf-8")) > self.limits.max_state_bytes:
            return unavailable(questions, "OVER_BUDGET: state bytes", self._receipt(status="OVER_BUDGET"))
        if self.clock() < self._open_until:
            return unavailable(questions, "CIRCUIT_OPEN", self._receipt(status="CIRCUIT_OPEN"))
        if self._model is None:
            try:
                self.handshake()
            except ConnectionError as exc:
                return self._failed(questions, f"INFERENCE_UNAVAILABLE: {exc}")
        payload = {"state": state, "questions": {n: q.to_wire() for n, q in questions.items()}}
        body = json.dumps(payload, sort_keys=True).encode("utf-8")
        request_digest = hashlib.sha256(body).hexdigest()
        started = self.clock()
        last = ""
        for _attempt in range(self.limits.retries + 1):
            remaining = self.limits.deadline_s - (self.clock() - started)
            if remaining <= 0:
                last = "DEADLINE_EXCEEDED"
                break
            try:
                status, raw = self.transport("POST", self.endpoint + "/v1/decide", body, remaining)
            except (OSError, TimeoutError) as exc:
                last = f"INFERENCE_UNAVAILABLE: {type(exc).__name__}"
                continue
            if status != 200:
                last = f"INFERENCE_UNAVAILABLE: HTTP {status}"
                if 400 <= status < 500:
                    break  # a refused request is not retried
                continue
            try:
                decoded = json.loads(raw)
            except json.JSONDecodeError:
                last = "INVALID: response is not JSON"
                break
            answers = parse_decision(questions, decoded)
            self._failures = 0
            latency = decoded.get("latency_ms") if isinstance(decoded, Mapping) else None
            return Advice(answers, self._receipt(
                status="ANSWERED", request_digest=request_digest,
                response_digest=hashlib.sha256(raw).hexdigest(),
                latency_s=round(self.clock() - started, 4),
                server_latency_ms=latency if isinstance(latency, (int, float)) else None,
                n_tokens=decoded.get("n_tokens") if isinstance(decoded, Mapping) else None))
        return self._failed(questions, last or "INFERENCE_UNAVAILABLE", request_digest)

    def _failed(self, questions: Mapping[str, Question], reason: str,
                request_digest: str | None = None) -> Advice:
        self._failures += 1
        if self._failures >= self.limits.breaker_failures:
            self._open_until = self.clock() + self.limits.breaker_cooldown_s
        return unavailable(questions, reason, self._receipt(status="UNAVAILABLE", reason=reason,
                                                           request_digest=request_digest))

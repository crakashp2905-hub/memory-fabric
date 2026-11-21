"""A FAKE loopback model server for integration tests (W20-08). Never inference.

It speaks the three Ollama endpoints the stack uses (``/api/tags``,
``/api/version``, ``/api/chat``) on 127.0.0.1 and answers each chat with the
scripted team's step, so a test can drive the real HTTP client, the preflight,
the model actor and the model team end to end without a model.

It cannot be mistaken for a model: the runtime version starts with ``FAKE``,
every digest starts with ``sha256:fake``, and the model team labels any run
against it ``FAKE_BACKEND_NOT_EVIDENCE``.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from memory_fabric.outcome_typed.observations import AgentObservation

from .outcome_episode import ScriptedTeam

FAKE_VERSION = "FAKE-not-a-model"
FAKE_MODEL = "fake-scripted:latest"
FAKE_DIGEST = "sha256:fake" + "0" * 60


def is_fake(runtime_version: Any, digest: Any) -> bool:
    """True for anything this server (or another declared fake) reports."""
    return (str(runtime_version or "").upper().startswith("FAKE")
            or str(digest or "").startswith("sha256:fake"))


class _Handler(BaseHTTPRequestHandler):
    team = ScriptedTeam()

    def log_message(self, *args: Any) -> None:  # keep test output quiet
        pass

    def _send(self, payload: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - http.server naming
        if self.path == "/api/version":
            self._send({"version": FAKE_VERSION})
        elif self.path == "/api/tags":
            self._send({"models": [{"name": FAKE_MODEL, "digest": FAKE_DIGEST, "size": 0,
                                    "details": {"quantization_level": "FAKE",
                                                "parameter_size": "0", "family": "fake"}}]})
        else:
            self._send({"error": "not found"}, 404)

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/chat":
            self._send({"error": "not found"}, 404)
            return
        request = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        messages = request["messages"]
        role = messages[0]["content"].split("You are the ", 1)[1].split(" ", 1)[0]
        step = self.team(role, AgentObservation.from_json(messages[1]["content"]))
        content = json.dumps({"intent": step.intent,
                              "arguments": json.loads(step.canonical_json())["arguments"]})
        self._send({"model": request["model"], "message": {"role": "assistant", "content": content},
                    "prompt_eval_count": 1, "eval_count": 1, "done": True})


class FakeLocalModelServer:
    """``with FakeLocalModelServer() as host:`` serves on a free loopback port."""

    def __enter__(self) -> str:
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return f"http://127.0.0.1:{self.server.server_address[1]}"

    def __exit__(self, *exc: Any) -> None:
        self.server.shutdown()
        self.server.server_close()

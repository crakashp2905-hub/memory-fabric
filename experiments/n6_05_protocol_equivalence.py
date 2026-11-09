"""Loopback-only protocol equivalence contract for HTTP, MCP and UTCP."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from memory_fabric.adapters.mcp import McpServer, _ToolError  # noqa: E402
from memory_fabric.tool_protocol import ToolProtocolError, discover_utcp  # noqa: E402

TOKENS = {"loopback-write-token": "writer", "loopback-read-token": "reader"}
TOOLS = ("lookup", "record")
MANUAL = {
    "utcp_version": "1.0.0", "manual_version": "1.0.0",
    "name": "loopback-memory-mock", "description": "Local test provider only.",
    "tools": [
        {"name": "lookup", "description": "Read one fixture record.", "consequential": False,
         "inputs": {"type": "object", "properties": {"record_id": {"type": "string"}},
                    "required": ["record_id"], "additionalProperties": False}},
        {"name": "record", "description": "Write one idempotent fixture record.",
         "consequential": True,
         "inputs": {"type": "object", "properties": {
             "record_id": {"type": "string"}, "content": {"type": "string"},
             "idempotency_key": {"type": "string"}},
             "required": ["record_id", "content", "idempotency_key"],
             "additionalProperties": False}},
    ],
}


class MockProvider:
    def __init__(self) -> None:
        self.records = {"seed-1": "coastal pump checklist"}
        self.calls: dict[str, int] = {protocol: 0 for protocol in ("http", "mcp", "utcp")}
        self._writes: dict[tuple[str, str], tuple[str, dict[str, str]]] = {}

    def invoke(self, protocol: str, token: str | None, name: str,
               arguments: Any) -> dict[str, Any]:
        self.calls[protocol] += 1
        if token not in TOKENS:
            raise PermissionError("authentication_required")
        if name not in TOOLS:
            raise ValueError("unknown_tool")
        if not isinstance(arguments, dict):
            raise ValueError("arguments_must_be_object")
        agent = TOKENS[token]
        if name == "lookup":
            if set(arguments) != {"record_id"} or not isinstance(arguments["record_id"], str):
                raise ValueError("invalid_arguments")
            record_id = arguments["record_id"]
            if record_id not in self.records:
                raise LookupError("record_not_found")
            return {"record_id": record_id, "content": self.records[record_id]}
        if agent != "writer":
            raise PermissionError("permission_denied")
        if (set(arguments) != {"record_id", "content", "idempotency_key"}
                or any(not isinstance(arguments[key], str) or not arguments[key]
                       for key in arguments)):
            raise ValueError("invalid_arguments")
        request_digest = hashlib.sha256(json.dumps(
            {"record_id": arguments["record_id"], "content": arguments["content"]},
            sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        key = (agent, arguments["idempotency_key"])
        existing = self._writes.get(key)
        if existing:
            if existing[0] != request_digest:
                raise ValueError("idempotency_conflict")
            return existing[1]
        record_id = arguments["record_id"]
        self.records[record_id] = arguments["content"]
        receipt = {"record_id": record_id, "content": arguments["content"]}
        self._writes[key] = (request_digest, receipt)
        return receipt


class _MockMcpServer(McpServer):
    """Use the production JSON-RPC dispatcher with the shared mock tools."""

    def __init__(self, provider: MockProvider) -> None:
        super().__init__(client=None, fabric=None)
        self.provider = provider
        self._request_auth = threading.local()
        self._handlers = {name: self._invoke(name) for name in TOOLS}

    def tools(self) -> list[dict[str, Any]]:
        return [{"name": name, "inputSchema": {"type": "object"}}
                for name in TOOLS]

    def handle_authenticated(self, request: dict[str, Any], token: str | None):
        self._request_auth.token = token
        try:
            return super().handle(request)
        finally:
            del self._request_auth.token

    def _invoke(self, name: str):
        def invoke(arguments: dict[str, Any]) -> dict[str, Any]:
            try:
                return self.provider.invoke("mcp", getattr(self._request_auth, "token", None),
                                             name, arguments)
            except (PermissionError, LookupError, ValueError) as exc:
                raise _ToolError(str(exc)) from exc
        return invoke


class _Handler(BaseHTTPRequestHandler):
    provider: MockProvider
    mcp_server: _MockMcpServer

    def log_message(self, *_: Any) -> None:
        return

    def _write(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, sort_keys=True).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path != "/utcp/manual":
            self._write(404, {"error": "not_found"})
            return
        self._write(200, MANUAL)

    def do_POST(self) -> None:
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 65_536:
                raise ValueError("invalid_body_size")
            body = json.loads(self.rfile.read(size))
            token = self.headers.get("Authorization", "").removeprefix("Bearer ") or None
            if self.path == "/mcp":
                response = self.mcp_server.handle_authenticated(body, token)
                if response is None:
                    self._write(202, {})
                    return
                self._write(200, response)
                return
            if self.path.startswith("/http/"):
                name = self.path.removeprefix("/http/")
                protocol = "http"
            elif self.path.startswith("/utcp/"):
                name = self.path.removeprefix("/utcp/")
                protocol = "utcp"
            else:
                self._write(404, {"error": "not_found"})
                return
            result = self.provider.invoke(protocol, token, name, body.get("arguments"))
            self._write(200, {"result": result, "isError": False})
        except PermissionError as exc:
            self._write(403, {"error": str(exc), "isError": True})
        except LookupError as exc:
            self._write(404, {"error": str(exc), "isError": True})
        except (ValueError, json.JSONDecodeError) as exc:
            self._write(400, {"error": str(exc), "isError": True})

def _request(url: str, method: str, token: str | None = None,
             payload: dict[str, Any] | None = None) -> tuple[int, dict[str, Any]]:
    data = None if payload is None else json.dumps(payload).encode()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=data, headers=headers,
                                     method=method.upper())
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def _call(base: str, protocol: str, tool: str, args: dict[str, Any], token: str) -> dict[str, Any]:
    if protocol == "http":
        status, payload = _request(f"{base}/http/{tool}", "POST", token,
                                   {"arguments": args})
        return payload["result"] if status < 400 else {"error": payload["error"]}
    if protocol == "mcp":
        status, payload = _request(f"{base}/mcp", "POST", token, {
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": tool, "arguments": args},
        })
        if status >= 400:
            return {"error": payload.get("error", "http_error")}
        result = payload["result"]
        return json.loads(result["content"][0]["text"]) if result["isError"] else json.loads(
            result["content"][0]["text"])
    status, payload = _request(f"{base}/utcp/{tool}", "POST", token,
                               {"arguments": args})
    return payload["result"] if status < 400 else {"error": payload["error"]}


def _workflow(base: str, protocol: str, provider: MockProvider) -> dict[str, Any]:
    if protocol == "utcp":
        status, manual = _request(f"{base}/utcp/manual", "GET")
        if status != 200:
            raise RuntimeError("UTCP loopback manual discovery failed")
        descriptors = discover_utcp(manual)
        if {descriptor.name for descriptor in descriptors} != set(TOOLS):
            raise ToolProtocolError("UTCP manual did not preserve the common tool set")
    if protocol == "mcp":
        status, response = _request(f"{base}/mcp", "POST", "loopback-write-token",
                                    {"jsonrpc": "2.0", "id": 0,
                                     "method": "tools/list", "params": {}})
        if status != 200 or {row["name"] for row in response["result"]["tools"]} != set(TOOLS):
            raise RuntimeError("MCP tool discovery differs from the common tool set")

    lookup = _call(base, protocol, "lookup", {"record_id": "seed-1"},
                   "loopback-write-token")
    record_args = {"record_id": "result-1", "content": "checked at site",
                   "idempotency_key": "n6-05-write-1"}
    write = _call(base, protocol, "record", record_args, "loopback-write-token")
    replay = _call(base, protocol, "record", record_args, "loopback-write-token")
    denied = _call(base, protocol, "record", {
        "record_id": "forbidden", "content": "must not be written",
        "idempotency_key": "n6-05-readonly-write",
    }, "loopback-read-token")
    unauthenticated = _call(base, protocol, "lookup", {"record_id": "seed-1"},
                            "unknown-loopback-token")
    return {"lookup": lookup, "write": write, "idempotent_replay": replay,
            "readonly_write": denied, "unauthenticated_read": unauthenticated,
            "record_count": len(provider.records),
            "tool_dispatch_calls": provider.calls[protocol]}


def run() -> dict[str, Any]:
    reports: dict[str, Any] = {}
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    base = f"http://127.0.0.1:{server.server_address[1]}"
    # The handlers share one deterministic provider for equivalent calls; the
    # write replay is idempotent across transport variants by construction.
    provider = MockProvider()
    _Handler.provider = provider
    _Handler.mcp_server = _MockMcpServer(provider)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        for protocol in ("http", "mcp", "utcp"):
            reports[protocol] = _workflow(base, protocol, provider)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    normalized = [{key: value for key, value in row.items() if key != "tool_dispatch_calls"}
                  for row in reports.values()]
    tool_calls_equal = len({row["tool_dispatch_calls"] for row in reports.values()}) == 1
    passed = (
        normalized[0] == normalized[1] == normalized[2]
        and tool_calls_equal
        and all(row["record_count"] == 2 for row in reports.values())
        and all(row["readonly_write"].get("error") == "permission_denied"
                for row in reports.values())
        and all(row["unauthenticated_read"].get("error") == "authentication_required"
                for row in reports.values())
    )
    return {
        "schema": "memory-fabric-n6-05-protocol-equivalence/1",
        "task_id": "N6-05", "acceptance_passed": passed,
        "evidence_level": "CONTRACT",
        "protocols": reports,
        "metrics": {"same_semantics": normalized[0] == normalized[1] == normalized[2],
                    "same_tool_work": tool_calls_equal,
                    "tool_calls_per_protocol": {key: row["tool_dispatch_calls"]
                                                 for key, row in reports.items()},
                    "same_write_permission": all(
                        row["readonly_write"].get("error") == "permission_denied"
                        for row in reports.values()),
                    "same_authentication_requirement": all(
                        row["unauthenticated_read"].get("error") == "authentication_required"
                        for row in reports.values()),
                    "paid_services_used": False,
                    "bind_host": "127.0.0.1"},
        "limitations": [
            "All three endpoints are a loopback contract harness over one mock provider; this is not a production protocol interoperability or external UTCP transport test.",
            "MCP is represented with JSON-RPC tools/list and tools/call messages over the loopback harness; the repository's production MCP adapter remains stdio-based.",
            "UTCP manual discovery uses the production parser, but tool calls are mapped by the mock harness to loopback routes and do not exercise public HTTPS, DNS, or TLS.",
            "One lookup, one idempotent write/replay, one read-only denial, and one unauthenticated call are measured; no latency or token-cost claim is made here."
        ],
        "source": {"commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                               check=True, capture_output=True,
                                               text=True).stdout.strip(),
                   "dirty_before_result_write": bool(subprocess.run(
                       ["git", "status", "--porcelain"], cwd=ROOT, check=True,
                       capture_output=True, text=True).stdout.strip()),
                   "experiment_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
    }


if __name__ == "__main__":
    result = run()
    out = ROOT / "research" / "results" / "n6-05-protocol-equivalence.json"
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"task_id": result["task_id"],
                      "acceptance_passed": result["acceptance_passed"],
                      "metrics": result["metrics"]}, indent=2))

"""Measure equivalent local tool workflows over direct SDK, MCP and UTCP paths.

No language model is called. Bytes are JSON application-body bytes; HTTP headers,
TCP framing and remote infrastructure charges are outside this local benchmark.
"""
from __future__ import annotations

import hashlib
import json
import math
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from experiments.n6_05_protocol_equivalence import (  # noqa: E402
    TOOLS,
    MockProvider,
    _Handler,
    _MockMcpServer,
)
from memory_fabric.tool_protocol import discover_utcp  # noqa: E402

SAMPLES = 20
TOKENS = {"write": "loopback-write-token", "read": "loopback-read-token",
          "invalid": "unknown-loopback-token"}


def _json_bytes(value: Any, *, sorted_keys: bool = False) -> bytes:
    return json.dumps(value, sort_keys=sorted_keys, separators=(",", ":")).encode("utf-8")


def _measure_http(base: str, path: str, payload: dict[str, Any] | None,
                  token: str | None, metrics: dict[str, Any]) -> tuple[int, Any, int, int, int]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{base}{path}", data=body, method="GET" if payload is None else "POST",
        headers={"Content-Type": "application/json",
                **({"Authorization": f"Bearer {token}"} if token else {})},
    )
    started = time.perf_counter_ns()
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            status, raw = response.status, response.read()
    except urllib.error.HTTPError as exc:
        status, raw = exc.code, exc.read()
    elapsed = time.perf_counter_ns() - started
    parsed = json.loads(raw)
    request_bytes, response_bytes = len(body or b""), len(raw)
    metrics["transport_round_trips"] += 1
    metrics["application_request_bytes"] += request_bytes
    metrics["application_response_bytes"] += response_bytes
    metrics["request_latencies_ns"].append(elapsed)
    return status, parsed, request_bytes, response_bytes, elapsed


def _direct_call(provider: MockProvider, name: str, arguments: dict[str, str],
                 token: str, metrics: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter_ns()
    request_bytes = len(_json_bytes({"tool": name, "arguments": arguments, "token": token}))
    try:
        result = provider.invoke("http", token, name, arguments)
        response = {"result": result, "isError": False}
    except (PermissionError, LookupError, ValueError) as exc:
        response = {"error": str(exc), "isError": True}
    metrics["transport_round_trips"] += 0
    metrics["application_request_bytes"] += request_bytes
    metrics["application_response_bytes"] += len(_json_bytes(response))
    metrics["request_latencies_ns"].append(time.perf_counter_ns() - started)
    return response.get("result", {"error": response.get("error", "unknown_error")})


def _workflow(protocol: str, base: str | None, provider: MockProvider) -> dict[str, Any]:
    metrics = {"transport_round_trips": 0, "application_request_bytes": 0,
               "application_response_bytes": 0, "request_latencies_ns": []}
    workflow_started = time.perf_counter_ns()
    cpu_started = time.process_time_ns()
    if protocol == "direct_sdk":
        # The direct SDK gets the same frozen tool registry from the local SDK
        # module; recording its serialized size makes schema discovery visible.
        discovered = tuple(TOOLS)
        if set(discovered) != {"lookup", "record"}:
            raise AssertionError("direct SDK tool registry mismatch")
        metrics["discovery_operations"] = 1
        metrics["application_request_bytes"] += 0
        metrics["application_response_bytes"] += len(_json_bytes(TOOLS))

        def call(tool: str, args: dict[str, str], token: str) -> dict[str, Any]:
            return _direct_call(provider, tool, args, token, metrics)

    elif protocol == "mcp":
        status, listing, *_ = _measure_http(base or "", "/mcp", {
            "jsonrpc": "2.0", "id": 0, "method": "tools/list", "params": {},
        }, TOKENS["write"], metrics)
        if status != 200 or {tool["name"] for tool in listing["result"]["tools"]} != {"lookup", "record"}:
            raise AssertionError("MCP tool discovery mismatch")
        metrics["discovery_operations"] = 1

        def call(tool: str, args: dict[str, str], token: str) -> dict[str, Any]:
            _, response, *_ = _measure_http(base or "", "/mcp", {
                "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": tool, "arguments": args},
            }, token, metrics)
            result = response["result"]
            return json.loads(result["content"][0]["text"])

    elif protocol == "utcp":
        status, manual, *_ = _measure_http(base or "", "/utcp/manual", None, None, metrics)
        if status != 200 or {row.name for row in discover_utcp(manual)} != {"lookup", "record"}:
            raise AssertionError("UTCP discovery mismatch")
        metrics["discovery_operations"] = 1

        def call(tool: str, args: dict[str, str], token: str) -> dict[str, Any]:
            status, response, *_ = _measure_http(base or "", f"/utcp/{tool}",
                                                  {"arguments": args}, token, metrics)
            return response["result"] if status < 400 else {"error": response["error"]}

    else:  # pragma: no cover - internal invariant
        raise AssertionError(protocol)

    lookup = call("lookup", {"record_id": "seed-1"}, TOKENS["write"])
    write_args = {"record_id": "result-1", "content": "checked at site",
                  "idempotency_key": "n6-09-write-1"}
    write = call("record", write_args, TOKENS["write"])
    replay = call("record", write_args, TOKENS["write"])
    denied = call("record", {"record_id": "forbidden", "content": "must not write",
                              "idempotency_key": "n6-09-denied"}, TOKENS["read"])
    unauthenticated = call("lookup", {"record_id": "seed-1"}, TOKENS["invalid"])
    result = {"lookup": lookup, "write": write, "replay": replay,
              "denied_write": denied, "unauthenticated_read": unauthenticated,
              "record_count": len(provider.records), "tool_calls": provider.calls["http"]
              if protocol == "direct_sdk" else provider.calls[protocol]}
    metrics["workflow_wall_ns"] = time.perf_counter_ns() - workflow_started
    metrics["workflow_cpu_ns"] = time.process_time_ns() - cpu_started
    metrics["tool_calls"] = result["tool_calls"]
    metrics["safe_completion"] = (
        lookup == {"record_id": "seed-1", "content": "coastal pump checklist"}
        and write == {"record_id": "result-1", "content": "checked at site"}
        and replay == write and result["record_count"] == 2
        and denied.get("error") == "permission_denied"
        and unauthenticated.get("error") == "authentication_required"
        and "forbidden" not in provider.records
    )
    metrics["modeled_token_count"] = None
    metrics["model_cost_usd"] = None
    metrics["external_service_cost_usd"] = 0.0
    metrics["wire_bytes"] = (metrics["application_request_bytes"]
                              + metrics["application_response_bytes"]
                              if protocol != "direct_sdk" else 0)
    return {"result": result, "metrics": metrics}


def _percentile(samples: list[int], percentile: float) -> int:
    ordered = sorted(samples)
    return ordered[max(0, math.ceil(percentile * len(ordered)) - 1)]


def run(samples: int = SAMPLES) -> dict[str, Any]:
    if samples < 5:
        raise ValueError("at least five samples are required")
    server = None
    thread = None
    base = None
    try:
        from http.server import ThreadingHTTPServer
        import threading

        server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        base = f"http://127.0.0.1:{server.server_address[1]}"
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        protocol_samples: dict[str, list[dict[str, Any]]] = {
            protocol: [] for protocol in ("direct_sdk", "mcp", "utcp")}
        for _ in range(samples):
            for protocol in protocol_samples:
                provider = MockProvider()
                _Handler.provider = provider
                _Handler.mcp_server = _MockMcpServer(provider)
                protocol_samples[protocol].append(_workflow(protocol, base, provider))
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        if thread is not None:
            thread.join(timeout=5)

    summary: dict[str, Any] = {}
    for protocol, rows in protocol_samples.items():
        metrics = [row["metrics"] for row in rows]
        result_sets = [row["result"] for row in rows]
        if any(result != result_sets[0] for result in result_sets[1:]):
            raise AssertionError(f"non-deterministic results for {protocol}")
        cpu_median_ns = int(statistics.median(m["workflow_cpu_ns"] for m in metrics))
        summary[protocol] = {
            "samples": samples,
            "safe_completion_rate": sum(m["safe_completion"] for m in metrics) / samples,
            "tool_calls_per_workflow": sorted({m["tool_calls"] for m in metrics}),
            "discovery_operations_per_workflow": sorted({m["discovery_operations"] for m in metrics}),
            "transport_round_trips_per_workflow": sorted({m["transport_round_trips"] for m in metrics}),
            "application_request_bytes_median": int(statistics.median(
                m["application_request_bytes"] for m in metrics)),
            "application_response_bytes_median": int(statistics.median(
                m["application_response_bytes"] for m in metrics)),
            "wire_body_bytes_median": int(statistics.median(m["wire_bytes"] for m in metrics)),
            "workflow_wall_ms_p50": round(statistics.median(
                m["workflow_wall_ns"] for m in metrics) / 1_000_000, 3),
            "workflow_wall_ms_p95": round(_percentile(
                [m["workflow_wall_ns"] for m in metrics], 0.95) / 1_000_000, 3),
            "workflow_cpu_ms_median": (round(cpu_median_ns / 1_000_000, 6)
                                        if cpu_median_ns > 0 else None),
            "workflow_cpu_measurement": ("MEASURED" if cpu_median_ns > 0
                                         else "BELOW_PER_WORKFLOW_CLOCK_RESOLUTION"),
            "model_tokens": None,
            "model_cost_usd": None,
            "external_service_cost_usd": 0.0,
            "result": result_sets[0],
        }
    semantic_equal = len({json.dumps(summary[p]["result"], sort_keys=True)
                          for p in summary}) == 1
    safe = all(row["safe_completion_rate"] == 1.0 for row in summary.values())
    call_equivalence = all(row["tool_calls_per_workflow"] == [5] for row in summary.values())
    passed = semantic_equal and safe and call_equivalence
    return {
        "schema": "memory-fabric-n6-09-orchestration-cost-benchmark/1",
        "task_id": "N6-09", "acceptance_passed": passed,
        "evidence_level": "CONTRACT", "sample_count": samples,
        "protocols": summary,
        "comparison": {"same_semantics": semantic_equal,
                       "same_tool_calls": call_equivalence,
                       "safe_completion_all_samples": safe,
                       "model_invocations": 0,
                       "model_token_savings_claimed": False,
                       "cost_accounting": "local wall latency and JSON application bytes measured; external service spend is zero; model cost is not applicable; per-workflow CPU time is reported only if the host clock resolves it"},
        "method": {"workflow": "lookup, authorized write, idempotent replay, read-only write denial, unauthenticated read denial",
                   "samples_per_protocol": samples,
                   "bind_host": "127.0.0.1",
                   "byte_scope": "JSON request/response bodies; excludes HTTP headers and TCP/IP framing",
                   "direct_sdk": "in-process callable mock provider using the frozen Python tool registry",
                   "mcp": "loopback HTTP bridge carrying the production MCP JSON-RPC dispatcher",
                   "utcp": "loopback HTTP calls after production UTCP manual parser discovery"},
        "source": {"commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                                check=True, capture_output=True,
                                                text=True).stdout.strip(),
                   "experiment_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
        "limitations": [
            "The direct SDK path is an in-process callable mock; it does not call an LLM provider SDK or a production remote service.",
            "MCP is measured over a loopback HTTP bridge around the repository's production JSON-RPC dispatcher, not its stdio framing.",
            "UTCP transport is a loopback HTTP mapping around the production parser; public DNS, TLS and remote server latency are not measured.",
            "Latency and CPU results describe this local Windows host and mock workload only; they are not general performance claims.",
        ],
    }


if __name__ == "__main__":
    report = run()
    (ROOT / "research" / "results" / "n6-09-orchestration-cost-benchmark.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"task_id": report["task_id"],
                      "acceptance_passed": report["acceptance_passed"],
                      "comparison": report["comparison"],
                      "summary": {key: {k: value for k, value in row.items()
                                        if k not in {"result", "samples"}}
                                 for key, row in report["protocols"].items()}}, indent=2))

# Error contract matrix

The surfaces use protocol-appropriate status/code shapes; clients must branch
on the documented code or structured field, not on display prose. A surface
that does not expose a capability is explicitly `N/A` rather than inventing a
second error for an operation it cannot perform.

| Case | Python SDK | MCP | Agent HTTP API | CLI |
|---|---|---|---|---|
| Invalid identity | `agent_for` raises `IdentityError`; covered by `tests/test_service.py` | N/A: MCP runs with a process-bound agent identity and has no caller credential field; attempts to impersonate via tool arguments are rejected by its validators | `401` with the same opaque body for missing, forged, expired and revoked credentials; `tests/test_agent_api.py::TestIdentityAndTenancy` | N/A: the CLI is a local operator surface; it does not accept agent bearer credentials |
| Invalid or withdrawn evidence | `NotUsable.decision.reason_code`; `tests/test_sdk.py` | tool result has `isError=true` and carries the same reason code; `tests/test_mcp.py` | `403` and an `error` payload carrying the same reason code; `tests/test_agent_api.py` | the operator can inspect withdrawn records; agent-facing retrieval is not a CLI command |
| Unavailable tool or operation | no dynamic tool-dispatch API is exposed | JSON-RPC `INVALID_PARAMS` error for an unknown tool; `tests/test_mcp.py::TestTheSurfaceIsNarrow` | `404` with `unknown operation`; `tests/test_agent_api.py::TestTheSurface` | argparse exit `2`; unsupported command is not treated as a successful operation |
| Stale correction preview | `correction.apply` raises `StalePreview` (`STALE_PREVIEW`); `tests/test_correction.py::StalePreviewsAreRefused` | extended MCP offers read-only preview only; there is no apply tool to accept stale state | agent HTTP API has no correction-apply endpoint | exit `5`, emits `STALE_PREVIEW`, leaves lifecycle unchanged; covered by `tests/test_correction.py::TheCommand` |

The HTTP and MCP reason payloads intentionally preserve the SDK's stable
decision reason code while wrapping it in each transport's native error
envelope. The JSON-RPC numeric protocol errors are used for unknown tools,
malformed requests and missing methods; refusals from an invoked tool use
`isError` and structured text.
See [API.md](API.md), [CLI.md](CLI.md), and [STABILITY.md](../STABILITY.md) for
surface-specific compatibility commitments.

# Decision models, System 1, UTCP, and governed Code Mode

Status: experimental. These components propose and transport actions; they do
not grant authority.

## Deterministic boundary

`memory_fabric.decision_models` defines typed options, probability-bearing
proposals, explicit abstention, calibration scoring, and risk-sensitive
System 1 to System 2 escalation. Every proposal is validated: probabilities
must be finite, cover exactly the declared options, and sum to one. Ties in the
dependency-free baseline abstain.

This API deliberately has no execution method. A selected option that names an
action must still be converted into an `ActionRequest` and authorized by
`ActionGate`. Model probability cannot add a grant, approve evidence, mint a
credential, or weaken a tool rule.

## Pinned UTCP subset

The adapter targets UTCP `1.0.x` manuals and requires both `utcp_version` and
`manual_version`. It reads tool `inputs` and either the current
`tool_call_template` form or the RFC's `tool_transport` spelling. Discovery is
pure parsing: it performs no call and grants no tool.

`ToolDescriptor` is the protocol-neutral representation. The MCP and UTCP
converters accept an explicit supported field set and reject unknown
descriptor or annotation fields, including security-related extensions. A
same-protocol round trip preserves supported fields. Cross-protocol conversion
fails when UTCP transport metadata or MCP annotations have no representation
in the destination protocol; callers must handle that error rather than lose
the field. MCP annotations remain descriptive hints and never authorize an
action.

Manual parsing pins `utcp_version` to `1.0.x` and `manual_version` to `1.0.0`.
Tool names, argument schemas, HTTP template shape, scheme, hostname, port and
method are validated before a descriptor is returned. The local policy accepts
HTTPS on the default port to syntactically public ASCII DNS names or globally
routable IP literals; it rejects local/reserved names, non-global IP literals,
credentials, encoded authority hosts, control characters, shell metacharacters,
and unsupported transport kinds. `validate_utcp_redirect` requires each
redirect to remain on the original public HTTPS origin. The parser performs no
file or network I/O. There is no UTCP transport executor in this package, so
callers must invoke redirect validation for every hop. Any future executor
must also validate resolved addresses at connection time and disable automatic
redirect following until each hop is checked; this parser alone cannot prevent
DNS rebinding or a server redirecting to a private address. Shell metacharacter
rejection is defense in depth; transport implementations must never invoke a
shell to make HTTP requests.

The pinned primary sources are:

- UTCP RFC 1.0.0: <https://www.utcp.io/about/RFC>
- UTCP 1.0 implementation guide: <https://www.utcp.io/next/implementation>
- Official specification repository: <https://github.com/universal-tool-calling-protocol/utcp-specification>

The specification was checked on 2026-10-31. UTCP remains a draft and its
manual vocabulary has changed before, so unsupported versions fail closed.

## Governed Code Mode

`CodeModePlan` is intentionally smaller than the upstream TypeScript sandbox.
It accepts a sequence of calls with literal keyword arguments. Imports,
attribute access, positional or expanded arguments, loops, expressions, file
access, network access, and arbitrary Python execution are rejected as plan
syntax. Evaluator and reflection builtins such as `eval`, `exec`, `open`,
`getattr`, and `__import__` are reserved and cannot be called as tool names.
The parser does not sandbox a registered handler: a tool may still perform
external effects, which remain subject to its own policy and action gate.

Each call is executed separately by `GovernedToolRuntime`. Its exact arguments
are bound into `ActionRequest`, authorization is rechecked immediately before
execution, and an idempotency key flows through `ActionGate.execute`. A loop or
retry can therefore never inherit authorization from an earlier effect.

The parser caps source at 64 KiB, a plan at 32 calls, total JSON-compatible
argument bytes at 32 KiB, and nested argument depth at 16. There is no branch,
loop, or recursive execution construct in the grammar. `GovernedToolRuntime`
dispatches only handlers present in its host-owned registry; an unknown name
fails before reaching the action gate.

Offline smoke tests can install `tools.offline_network_guard` in an isolated
Python process. It denies non-loopback DNS and socket connection attempts with
an explicit `PermissionError`, while allowing loopback destinations for mock
providers. The regression test verifies a public-address request is denied
before host-file access and confirms loopback resolution remains permitted.
This process-local monkeypatch is test defense in depth; it is not a security
boundary against native code, direct system calls, or a compromised process.
Production execution of untrusted handlers still requires an OS-level sandbox
and independent egress policy.

## Research status

The API and security invariants are implemented and locally testable. Claims
about Laya, Jev, encoder models, model-family robustness, latency, token cost,
or comparative MCP/UTCP/Code Mode efficiency require registered datasets and
runs. They remain research gates rather than being inferred from this API.

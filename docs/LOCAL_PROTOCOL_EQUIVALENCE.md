# Local HTTP, MCP and UTCP workflow comparison

`experiments/n6_05_protocol_equivalence.py` runs one common mock-provider workflow through HTTP calls, the production `McpServer.handle` JSON-RPC dispatcher, and UTCP manual discovery via the production `discover_utcp` parser. The HTTP server binds only to `127.0.0.1` and an operating-system-selected ephemeral port. The test needs local socket permission; it makes no external network calls and uses no paid service.

Each path lists or discovers the same `lookup` and `record` tools and performs the same five dispatches: read one fixture record, write one record, replay the idempotent write, try a write with a read-only token, and try a read with an unknown token. Authentication, authorization, argument validation, idempotency, resulting records and dispatch counts come from the same deterministic provider. The test compares normalized results and requires equal work and permission outcomes.

The UTCP manual itself is served from loopback and parsed by the production parser. The mock maps the discovered tool names to loopback routes; this does not exercise a public HTTPS transport, DNS or TLS. MCP's production adapter remains stdio-based; the loopback bridge carries real JSON-RPC messages to its protocol dispatcher. These results are local contract evidence, not a claim of production cross-vendor interoperability.

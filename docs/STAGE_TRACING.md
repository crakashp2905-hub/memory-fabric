# Local request stage tracing

`AgentApi(..., trace_recorder=StageTraceRecorder())` enables a bounded in-memory
ring of timing-only request traces. The HTTP request records body decoding,
authentication, event append, projection, duplicate-copy lookup, JSON
serialization, and socket transport. Remaining handler work is retained under
`dispatch_other`. Each row has a request ID, operation, integer nanosecond
durations, total duration, reconciliation error, and a validator.

The recorder is opt-in, thread-safe, and capped at 10,000 rows by default.
Trace rows contain no credentials, query, body, memory content, or identifiers
other than a generated request ID. The timing gate checks the sum against the
end-to-end request duration (allowing 2 ms of instrumentation-boundary drift).

`tests/test_stage_trace.py` validates malformed and unbalanced rows, then
issues a real localhost write and checks all required stages appear in its
single end-to-end record. This is local process instrumentation; transport
time measures response serialization and socket writing on the server, not
client network latency.

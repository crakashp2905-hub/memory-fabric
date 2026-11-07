# Interrupted action reconciliation

An external side effect and Memory Fabric's SQLite transaction do not share an atomic commit. A process can perform the effect and die before writing `ActionExecuted`; the durable `ActionAttempted` row then means **unknown**, not success and not failure. A callback exception or timeout is also unknown because the effect may have happened before the error or may still finish after the fence is released.

`memory_fabric.actions.reconciliation_ledger(fabric)` derives the latest state for each idempotency key from the append-only action events:

- `completed`: a successful fenced `ActionExecuted` receipt exists.
- `definitely_unexecuted`: the authorization gate recorded a refusal before invoking the callback.
- `unknown`: an attempt has no receipt, the callback failed, or the action timed out/released its fence. Operator reconciliation is required.

The ledger reports IDs, tool, tenant, agent, payload digest, policy version, tool digest, event sequence and attempt count; it never claims to inspect the external system. Each `ActionExecuted` event also records the evidence memory IDs and versions plus the outcome. Configure `ToolRule.tool_digest` with the host's SHA-256 digest of the registered descriptor; when omitted, Memory Fabric hashes the canonical gate rule and tool name. That fallback identifies the policy-facing tool rule, not executable code. Check the external system's own receipt/state, preserve the evidence, then retry only with the same idempotency key when that system deduplicates it. Never manufacture a local success receipt for an unknown external outcome.

`tests/test_action_reconciliation.py` checks all three states. `tests/test_action_execution_receipt.py` checks outcome, evidence version, policy version, tool digest, replay reconstruction and secret redaction. `tests/test_action_crash.py` terminates a child after a mock external effect, reopens the persistent store, and confirms the action remains unknown. This verifies local bookkeeping and crash semantics, not exactly-once behavior of arbitrary external tools.

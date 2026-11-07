# Action-key idempotency

`ActionGate.execute` stores a digest of the tool, agent, tenant, target, canonical parameters, and certificate evidence versions with each `ActionAttempted` and `ActionExecuted` event. Reusing a key with a different digest returns `idempotency_key_payload_mismatch` and does not call the tool. Replaying the same completed request returns `already_executed`. A failed or uncertain same-payload attempt still requires explicit `retry=True` and fresh authorization.

The event digest contains no action content or parameters. Older action events without the digest cannot prove payload equality; reuse of those keys fails closed. The host must reconcile their external outcome before choosing a new key. A remote effect must also honor the idempotency key: Memory Fabric cannot atomically commit a separate system's side effect and its local receipt.

`tests/test_action_fence.py` verifies same-payload replay, mismatched-payload rejection, and a lost-response retry against a mock effect that deduplicates by key. `tests/test_action_crash.py` verifies the unresolved-crash path requires an explicit retry.

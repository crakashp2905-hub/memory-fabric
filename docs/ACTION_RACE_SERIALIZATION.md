# Correction, retrieval, and action serialization

Protected effects use the store transaction as a fence: certificate
verification, evidence-version checks, the tool invocation, and the
`ActionExecuted` receipt are serialized against local lifecycle writes.

`tests/test_action_race_barriers.py` forces both authoritative orderings with
threading events rather than scheduler sleeps:

1. If an action has entered the fenced tool call, a concurrent correction
   cannot commit. The action and receipt commit first; the correction follows
   at a higher log sequence.
2. If retrieval exposes version 1 and a correction commits before action
   authorization, the old certificate is refused with
   `evidence_version_moved`; the tool has no effect and the `ActionExecuted`
   audit receipt records a refusal rather than a successful effect.
3. Even when planning first obtains an allowed authorization, a correction
   committed before `execute` makes the old certificate stale. `execute`
   performs its own live authorization inside the transaction fence; it does
   not accept or reuse the earlier `ActionDecision` snapshot.

The guarantee is intentionally local and transactional. A correction that is
not yet visible in this store cannot be known. Imported evidence therefore has
separate freshness leases and retraction delivery requirements. External tool
systems also need idempotency because a process can die after an external
effect but before recording its outcome.


# Evidence risk by operation

`AgentClient.recall` accepts a typed `EvidenceOperation`; the SDK derives the minimum integrity risk and applies it to each returned memory. `fetch` uses the same policy and permits callers to strengthen the default, never weaken it.

| Operation | Default risk | Effect |
|---|---|---|
| `read` | low | Return usable evidence; contested material can be surfaced with a warning when requested. |
| `summarize` | low | Read evidence for a summary while retaining contested warnings and evidence tokens. |
| `recommend` | medium | Require revalidation for contested or otherwise medium-risk evidence. |
| `execute` | high | Cannot be requested through recall/fetch. Reverify the evidence at high risk and pass the action through `ActionGate`, which checks tool grants, certificates, policy, approvals, and action binding before effects. |

Low-risk access does not grant a side-effect capability. `AgentClient.verify` rejects a lower risk, and the action gate independently verifies at high risk. The policy is a minimum threshold; a caller may choose a stricter risk for a read.

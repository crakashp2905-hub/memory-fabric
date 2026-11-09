# Operator health levels

`GET /api/health` reports a read-only, point-in-time service check. The
Control Center runs it only when an operator selects **Run full store health
check**, because event-chain verification reads the full log.

| Level | Meaning | Consequential actions |
|---|---|---|
| `healthy` | Store read, event-chain verification, and pending-delivery query all succeeded; no retractions are awaiting delivery. | The health check itself permits normal action checks; every action still passes through its ordinary authorization gate. |
| `degraded` | Store and event integrity are readable and valid, but at least one correction delivery remains unsettled. | Existing action gates continue to decide; operators should inspect federation delivery and stale-evidence controls. |
| `unsafe-to-execute` | Event integrity failed, or a required health check could not be completed. | Do not execute consequential actions until the cause is resolved and health is rechecked. |
| `unavailable` | The service could not read the store or its basic health state. | The health result permits no actions; restore service and recheck. |

The result includes check states and stable reason codes. It omits exception
messages, memory content, identifiers, and peer names. A pending correction is
counted per outbox delivery. This is a diagnostic snapshot, not a lock held
through a later action and not a substitute for the action-time authorization
gate. A successful chain check proves consistency with the local chain, not
that an attacker with database and checkpoint control did not rewrite it.

The endpoint catches read and verification failures and reports a non-healthy
level; it does not convert a failed check into `healthy`. The chain check is a
full scan and therefore runs only on explicit request, not on ordinary SLO
polling.

# When a plain vector store is enough

Memory Fabric adds policy, provenance, correction propagation, evidence checks and action authorization around retrieval. Those controls add storage, evaluation and operating cost. Use a plain vector index when the job is semantic lookup and the consequences of a stale or wrong passage are handled elsewhere.

## Prefer ordinary vector retrieval when

- The corpus is mostly static or can be rebuilt after edits.
- A returned passage is a suggestion for a person, not evidence that directly authorizes a consequential tool call.
- One application or tenant owns the corpus, so per-tenant authorization is unnecessary.
- You do not need a durable record of who asserted a claim, which sources support it, or what changed after correction.
- A simple retrieval quality and latency benchmark shows that the extra governance path does not improve the task you care about.

For a deterministic five-seed long-running-task world, both `vector_append` and `vector_replace` matched the oracle at 100% completion and zero harmful actions over 600 jobs; that registered experiment was abandoned because it had no headroom to demonstrate a Memory Fabric advantage. This is evidence that governance was unnecessary in that world, not a universal result ([L1 report](../../research/results/l1-long-running.md)). In DepotWorld, the perfect-selection oracle had only 2.5–5 percentage points of headroom over pooled vectors, so the registered comparison was again declared uninformative before attributing benefit to governance ([X4 report](../../research/results/x4-governed-vs-pooled.md)).

## Consider Memory Fabric when

- Corrections or retractions must invalidate dependent claims and decisions.
- Multiple agents contribute evidence and copied claims must not count as independent corroboration.
- A consequential action needs a deterministic authorization check against current evidence and policy.
- Tenant, provenance, withdrawal, or action history must be inspectable and replayable.
- You can measure a material reduction in stale or unsafe actions that justifies the added latency and operational surface.

These are selection criteria, not proof that Memory Fabric improves every workload. Start with a matched task set, count valid actions as well as retrieval hits, and retain the vector baseline.

## Account for the cost

Memory Fabric maintains an event log and projections, performs authorization and evidence checks, and requires operators to manage keys, backups, upgrades and recovery. The local authenticated 50-client HTTP capacity run completed its operations but measured 4.3–4.8 operations per second and a 24.2-second mean p99; it failed its release performance thresholds. This is a single-host Windows result, not a general capacity bound ([capacity report](../../research/results/master-checklist-http-capacity-v1.md)). A plain vector store may be the better engineering choice when those controls do not change the outcome.

No buyer demand or revenue conclusion follows from these technical comparisons.

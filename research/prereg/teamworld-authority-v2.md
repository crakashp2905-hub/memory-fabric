# TeamWorld authority-conditioned corrections v2 — confirmation protocol

Registered after development on seeds 101–105. Those seeds may not confirm
this protocol. Confirmation uses unseen seeds 201–205, 50 agents and 60 rounds.

## Question

Does transmitting an independent verification signal for a correction, and
recording it as a new version of the canonical typed claim, improve decisions
without weakening withdrawal safety?

## Fixed arms

- `fabric`: the v1 adapter, which submits corrections as ordinary writes.
- `fabric_authority`: versions the canonical claim, quarantines exact competing
  records, validates the independently remeasured version and records elevated
  authority from `world-verifier`.
- `shared`, `oracle`: context and ceiling arms, unchanged.

The deterministic agent, `k=5`, task schedule, correction schedule and
rediscovery rules are unchanged from grand-50-agent-suite-v1.

## Primary acceptance rules

- `fabric_authority` stale-action rate is zero.
- Task success exceeds `fabric` on the same five seeds.
- Valid-evidence withholding is lower than `fabric` on the same five seeds.
- No arm exceeds the oracle.

The original absolute targets (task success above the best non-oracle baseline
and withholding at most 5%) are reported but are not silently weakened. A
relative win that misses either target is an improvement, not release
qualification.

## Required reporting

Bind the result to commit, dirty-tree state, seeds, agent count and rounds.
Report task success, stale actions, withholding, abstention and the new
`evidence_miss_reasons` counts for both Fabric arms. Report failures beside
passes.

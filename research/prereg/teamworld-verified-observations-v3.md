# TeamWorld verified observations v3 — confirmation protocol

Registered after the authority-conditioned v2 confirmation and before running
this arm. Development uses seeds 301–305. Confirmation, if development meets
the safety rule and improves task success, uses untouched seeds 401–405. Both
runs use 50 agents, 60 rounds, 100 tasks per seed and retrieval `k=5`.

## Question

Does attaching a trusted-observation signal to facts produced directly by a
measuring instrument reduce governance holds while preserving correction
safety?

## Fixed arms

- `fabric_authority`: v2, where independently remeasured corrections carry
  authority but ordinary discoveries remain agent assertions.
- `fabric_verified`: the same correction behavior, plus validation and
  elevation for direct observations supplied by the trusted world sensor.
- `shared`, `oracle`: unchanged context and ceiling arms.

This is provenance conditioning, not confidence-based authorization. Only the
benchmark's explicit sensor boundary may attach `world-verifier`; retrieved
text, model output, copied memories and ordinary agent assertions cannot.

## Primary acceptance rules

- `fabric_verified` stale-action rate is zero.
- Task success exceeds `fabric_authority` on the same five seeds.
- Valid-evidence withholding is lower than `fabric_authority`.
- No arm exceeds the oracle.

The original absolute targets remain task success above the best non-oracle
baseline and withholding at most 5%. Missing either is reported as failure,
even if all relative rules pass.

## Required reporting

Bind results to the exact commit, dirty-tree state, seeds and configuration.
Report task success, stale action, withholding, abstention and evidence-miss
reasons. Development and confirmation results must remain separately labelled.

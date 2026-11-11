# N4-07 compaction comparison preregistration

**Status:** frozen before the experiment run. This is a simulated, deterministic
agent contract study; it is not a real-agent or product-performance claim.

## Question

On identical temporal-preference tasks, how do no compaction, naive recency,
extractive summary, and provenance-preserving summary compare on task success,
false stale actions, context bytes, and source reconstruction?

## Design

- Five fixed seeds: `11, 23, 37, 41, 59`.
- Each seed generates four subjects, each with two conflicting preferences over
  disjoint half-open valid-time intervals, plus eight unrelated records.
- Every subject is queried at both world times, for 40 total tasks and 8 tasks
  per seed. Records are shuffled only with an injected `random.Random(seed)`.
- Arms share the same store, task set, deterministic answer rule and records.
- `no_compaction` exposes all source records. `naive_recency` exposes the most
  recent records that fit the preregistered record-count cap of six.
- `extractive_summary` exposes the ordinary summary text, without source
  metadata. `provenance_preserving_summary` exposes summary text, source
  metadata and a verified dependency map, and may resolve records by exact
  source ID/version.
- A task succeeds only when the arm returns the sole preference whose valid
  interval contains the query time. Abstention is a failure. A false stale
  action is a returned preference that is not valid at that time.
- Context size is exact UTF-8 bytes of the serialized arm payload. Compression
  factor is full-source payload bytes divided by exposed payload bytes. These
  byte figures are not token or model-cost estimates.
- Identity reconstruction fidelity is the fraction of all source ID/version
  pairs recoverable from the arm payload. Factual reconstruction fidelity is
  the fraction of all source texts recoverable verbatim.

## Acceptance and interpretation

The acceptance is a complete, reproducible four-arm report with all four
metrics, all 40 tasks per arm, five seed-level rows, exact source SHA, fixture
digests and explicit simulation labels. No improvement threshold is registered;
this is a descriptive comparison. Any arm that beats the full-history upper
baseline, any duplicate/missing task, or any false stale action in the
provenance-preserving arm invalidates the run and must be investigated rather
than hidden. No arm may be described as superior from this fixture alone.

## Reproduction

Run `python -m experiments.n4_07_compaction_comparison` after the exact source
commit. The output is `research/results/n4-07-compaction-comparison.json` and
`.md`; focused tests are recorded separately in JUnit XML.

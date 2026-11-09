# N4-09 summary refresh profiling preregistration

**Status:** frozen before the experiment run. Deterministic local contract and
operation-count profiling; no wall-clock or production scaling claim.

## Question

After repeated corrections affect one session, does targeted invalidation and
refresh recompute only affected summaries, compared with rebuilding all session
summaries?

## Design

- Five fixed seeds: `13, 29, 43, 61, 79`.
- Each seed creates six sessions with eight consequential source facts each and
  an initial summary per session.
- Three sequential corrections target three distinct facts in session zero.
- The affected-refresh arm calls `recompact` after each correction. This is a
  complete deterministic rebuild of the affected session summary, not an
  in-place patch to summary text.
- The full-rebuild arm calls `compact_session` for every session after each
  correction.
- Primary metrics: summary recomputation count per correction; unaffected
  summary content stability; final affected-summary content hash; and equality
  of normalized final summaries across repeat runs with the same seed.
- Every arm sees the same source facts and corrections. All operation counts
  include initial and post-correction summary writes separately.

## Acceptance and interpretation

The report must contain all five seeds, both arms, correction-level counts and
hashes. Targeted refresh passes the boundedness condition only if exactly one
session is recomputed after each single-session correction, unaffected
summaries remain byte-identical, and same-seed reruns produce the same
normalized result. Any missing correction or stale active summary invalidates
the run. The comparison is descriptive; no latency, throughput, or universal
incremental-update claim is made.

## Reproduction

Run `python -m experiments.n4_09_summary_refresh` after the exact source
commit. Outputs are stored under `research/results/n4-09-summary-refresh.*`.

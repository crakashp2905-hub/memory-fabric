# Causal replay limitations

This document is updated from executed local evidence. A design proposal is
not a result.

## Fully local reproducibility envelope

- **Exact deterministic replay:** the low-level runner accepts only the
  built-in data-only updater, simulator, and policy plus an explicit complete
  ordered observation trace. It makes no original-decision provenance claim.
  Recorded-decision replay additionally requires the immutable source receipt,
  matching implementation digests, and current evidence authorization. The
  executor recomputes proposals and state fingerprints locally; a stored choice
  is not a substitute for computation. The result is a policy re-execution,
  not reconstruction of an unrecorded human or hosted-model rationale.
- **Seeded stochastic continuation:** the repository can capture and restore
  Python MT19937 algorithm identity, full internal state, position, and cached
  Gaussian value. A seed alone is insufficient. The current replay executor
  does not register a stochastic policy/tool handler, so these snapshots can
  restore local RNG state but do not make an otherwise unsupported stochastic
  decision replayable or eligible for an exact certificate.
- **Opaque or incomplete histories:** hosted-model internals, unavailable
  tool outputs, missing policy versions, absent RNG state, partial evidence,
  and changed or unreadable source versions cannot be reconstructed from
  current beliefs or prose. They must fail with typed `NON_REPLAYABLE`,
  `ERASED`, or `UNAUTHORIZED` outcomes as applicable.
- **Execution boundary:** there are no hosted provider modes in the CDM replay
  path. Replay accepts explicit immutable data records and performs no network,
  model, or real-tool call. Synthetic replay does not establish physical-world
  causal truth.

- The current local checkpoint has a toy Bayesian updater, evidence replay,
  certificate checks and one synthetic battery demonstrator. It is not the
  full registered benchmark suite and has no independent organizational
  evaluator.
- Historical query support is bounded to explicit IDs and current plus
  historical authorization. It is archival and cannot authorize current
  actions. See [Historical reads](HISTORICAL_READS.md).
- Exact replay is limited to deterministic, versioned policies and simulators
  whose complete inputs are captured. A seed alone is not sufficient for an
  opaque stochastic continuation.
- Generated worlds cannot establish physical-world causality, independent
  validation, external novelty or improved deployment accuracy.
- Replay certificates distinguish simulator/internal estimands from physical
  counterfactuals, which never verify as supported exact claims. Minimality
  claims are supported only when the certificate issuer supplies an
  independently verified complete coalition table of at most 10 players.
  `verify_with_minimality_proof` re-enumerates that table and binds its digest
  to the certificate. This proves a claim about the supplied deterministic
  table only; it does not prove the simulator produced that table honestly.
  Physical counterfactuals and incomplete tables remain unsupported.
- Pairwise interaction screens are exact only for the supplied complete
  coalition-value table and registered deterministic estimand. They do not
  establish source truth or general causal structure outside that table.
- A dependency edge, citation, exposure or authorization does not by itself
  establish that evidence changed an agent's choice.
- Simulation must not execute real actions. Any real tool result is represented
  only as a recorded observation or an allowlisted pure mock.
- CDM capture accepts a `MemoryService.Session` and rechecks its credential
  before and after a bounded, non-exposing historical snapshot. Direct
  `MemoryFabric` callers remain trusted in-process callers; the session is the
  service-level identity boundary.
- Decision records, tool observations and certificate commitments are typed,
  but automatic capture of original options, constraints, citations, RNG state,
  tool outputs, and complete decision traces remains unimplemented.
- The exact enumerator is intentionally small and exponential in node count;
  no scalability or 16 GB upper-bound claim is supported yet.
- Replay budget memory is a preflight estimate, not an allocator-enforced cap;
  CPU hard limits and interruption-safe teardown are not implemented. The
  in-memory checkpoint cache is bounded and revalidates authorization, but it
  is not a persistent snapshot store or a concurrent multi-process cache.
- Dependency-frontier scheduling currently identifies a conservative suffix;
  it does not prune replayed events. No exactness or speedup claim is made for
  selective replay until it is compared step-for-step with full suffix replay.
- The synthetic battery world separates cooling failure, overheating, sensor
  bias, and sensor readings, but its parameters are illustrative and not
  calibrated against physical battery data. Contradictory reports remain in
  the trace; the current engine declines to condition on a conflicted
  variable until a declared sensor model can interpret them.

Required evidence for removing any limitation is an offline test/benchmark
artifact linked from the task ledger, including raw outcomes, source digest,
frozen seed and known failure cases.

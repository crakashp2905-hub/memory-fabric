# CDM internal GO / NO-GO decision

Decision date: 2026-11-09  
Decision owner: Memory Fabric maintainers  
Scope: the current in-house, offline CDM implementation and its synthetic
qualification artifacts.

## Decision

**GO** for continued internal, offline research and engineering against the
explicitly bounded deterministic simulator and synthetic fixtures, provided
all claims retain the limitations in
[CDM known findings](CDM_KNOWN_FINDINGS.md).

**NO-GO** for deployment efficacy claims, autonomous correction or deletion,
physical-world causal claims, hosted-model reasoning reconstruction, or use of
CDM certificates as action authority. No independent or physical-world
validation supports those uses.

## Evidence considered

- The latest required local qualification record is
  [`research/results/cdm/offline-qualification/manifest.json`](../research/results/cdm/offline-qualification/manifest.json).
  Its status, checkout revision, source digest, focused checks, compatibility
  suite, benchmark stages, and limitations govern this decision. A FAIL or
  missing required stage makes internal qualification NO-GO until repaired.
- The corrected held-out comparison reports non-positive intervention point
  estimates and intervals including zero; it supplies no evidence of improved
  outcomes.
- The R5 v3 confirmatory interval crosses the frozen superiority margin.
- The correction-aware utility fixture does not justify replacing dependence
  routing with CDM review routing.
- The RNG receipt protects against state substitution after recording, but an
  authorized writer's initial RNG claim has no independent runtime attestation.
- The implementation remains a local deterministic replay and review system;
  it has no action entitlement and no real-tool execution path.

## Conditions for reconsideration

Any broader GO requires a new dated decision backed by independent evaluation,
realistic domain data, preregistered outcome tests that pass their frozen
thresholds, verified deployment isolation and resource limits, and a security
review of the intended integration. Do not revise this decision from a passing
synthetic gate alone.

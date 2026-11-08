# Causal replay API (experimental proposal)

The v1 facade is additive and opt-in. It uses only the Python standard
library and existing Memory Fabric APIs. No network access, model call, external
tool execution, or database schema change is required.

## Contract

```python
capture(fabric, verified_session, evidence_ids, *, known_at, valid_at=None,
        max_events=10_000) -> CaptureResult
restore(capture, *, updater_id, policy_id) -> RestoredState
intervene(capture, evidence_id, operation, replacement=None) -> Intervention
replay(state, intervention, *, simulator_id, max_steps=1_000) -> ReplayResult
evaluate(factual, counterfactual, *, evaluator_id, hidden_truth=None) -> EffectReport
certify(capture, intervention, replay_result, *, verifier_id) -> ReplayCertificate
verify_certificate(certificate, *, verifier_id) -> Verification
```

The table describes the complete intended facade; the current implementation
is deliberately narrower. Implemented operations are bounded capture,
correction impact, typed finite Bayesian update, evidence intervention,
deterministic replay (including explicit policy-swap labeling), and certificate issue/verify. `restore`, blinded
`evaluate`, a general policy registry, RNG capture, and durable trace storage
remain design targets. `record_decision` requires a verified session with
write permission and appends a digest-only CDM decision event; option and
constraint text are not stored in its payload. Later capture checks the record
digest against that event and the event hash chain. `execute_recorded` verifies
the receipt and resolves the recorded policy ID and source/configuration digest
against the local built-in policy. Unresolvable policy code or an option absent
from the original decision refuses exact replay. Capture accepts a `MemoryService.Session` bound to the
same fabric. It re-verifies the credential before and after a bounded snapshot,
uses no exposure-producing retrieval call, and returns only content
commitments. `known_at` is an inclusive event-log sequence;
`valid_at` is a separate validity-time point.
Capture accepts explicit IDs and respects the existing 100-ID / bounded-event
historical-read limits. Any request beyond budget refuses as a whole.

Each capture also binds a typed, digest-only decision trace to its selected
authorized evidence. It distinguishes retrieval availability, exposure
decisions (including withheld events), citations, and a recorded decision when
the caller supplies its verified receipt. Event references contain only the
event ID, sequence, event digest, class, selected evidence ID/version, and the
exposure boolean where applicable. Retrieval query text and unrelated
candidates are not copied into the CDM artifact. The trace is included in the
capture factual digest and strict record serialization. It represents recorded
events, not proof that an agent cognitively used cited or exposed evidence.

For a contemporaneous decision, first call `record_decision` with the option
set, selected option, constraints, evidence references, policy ID and
`ThresholdPolicy.implementation_digest`. It returns a record bound to a
session-authenticated append-only event. Pass that record to `capture`, then
use `execute_recorded` to re-execute the locally pinned policy against the
recorded evidence trace. `ReplayExecution.execution_kind` is
`policy_reexecution`; the recorded selected text is never substituted for a
recomputed proposal. This API does not claim to reconstruct an unrecorded
human or hosted-model decision. The generic low-level `execute` path also makes
no original-decision provenance claim.
For certificates tied to recorded replay, use
`issue_verified_recorded_replay`: it verifies the immutable receipt, recomputes
factual and counterfactual proposals, and requires independent verification of
both traces. Stochastic decisions and tool observations without independently
verified handlers refuse with `NON_REPLAYABLE`; a raw serialized status is not
evidence that such a trace was replayed.
If a stochastic component is present, pass a full `RNGSnapshot` from
`capture_rng_state`; a seed alone is not accepted. Deterministic built-in policy
records explicitly mark RNG state not applicable. Missing state refuses exact
recorded replay. Tool observations declare `exogenous`, `simulated_endogenous`,
or `opaque`; exact replay currently refuses tool observations because no pure
tool handler registry is implemented. `create_execution_checkpoint` can bind a
complete exact local replay prefix to its observations, per-step trace, state
fingerprint, simulator configuration, and policy implementation digest.
`execute_from_checkpoint` checks those commitments, reproduces the prefix to
verify it, then returns the full exact trace after adding the suffix. This
integrity checkpoint does not carry authorization: captured memory references
still require current access checks. Prefix verification currently recomputes
the prefix, so this API establishes continuation equivalence but does not claim
a replay-time speedup. Archival checkpoints record whether RNG continuation is
fully captured, deterministically inapplicable, or missing.
`verify_checkpoint_exact_ready` rechecks current access and evidence, model and
policy digests, observation completeness, and RNG state before an exact
checkpoint restore is eligible; an archival checkpoint without complete
inputs remains non-replayable.
The pure executor accepts only a tuple of immutable `Observation` records; it
rejects a live `MemoryFabric` or `CaptureResult` in place of that trace and
never reads the present-day projection. The authorized historical capture
layer binds evidence to `known_at` and current permissions. For evidence-bound
replay, `execute_captured` currently supports the registered
`memory-fabric-boolean-observation-json-v1` adapter. It parses only canonical
JSON content with schema `memory-fabric-observation-v1` and exactly the fields
`schema`, `variable`, and boolean `value`, using the exact authorized
historical memory version. Observation identity, origin, and sequence come
from that captured reference and event history. Caller-supplied observations,
when provided, must equal the adapter output exactly. The result includes the
adapter ID and source digest. Unknown adapters and unsupported content formats
refuse; adapters are not caller callbacks.

## Versioned belief-state schema

`BeliefState.to_dict()` serializes schema `memory-fabric-cdm-v1` with a sorted
variable list, normalized posterior probabilities, explicit per-variable
uncertainty, ordered observations, evidence references, conflict variables,
the updater/policy digest, and a fingerprint. The first-party field/type
contract is generated by `generated_belief_state_schema()` and checked in at
[`docs/schemas/cdm-belief-state-v1.json`](schemas/cdm-belief-state-v1.json).
`validate_belief_state_record()` rejects unknown/missing fields, invalid
probabilities, inconsistent uncertainty, malformed references and undeclared
conflicts. Its contract fixture is tested against the generated schema so the
artifact cannot silently drift. Belief values are diagnostic inputs only:
they do not modify a source memory's lifecycle, bypass current authorization,
or make withdrawn/erased evidence capturable. Capture checks the event history
and current governance separately for every reference.

Versioned records round-trip with `serialize_record` and `parse_record`; parsers
reject unknown fields and malformed nested references. This runnable example
round-trips the example decision record and demonstrates that an unknown field
is refused:

```json
{"agent_id":"diagnostic-agent","constraints":["human-review-required"],"evidence":[{"belief_id":"memory-17","digest":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","tenant_id":"tenant-a","version":2}],"options":["monitor","investigate"],"policy_digest":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","policy_id":"threshold-v1","schema":"memory-fabric-cdm-v1","selected":"investigate","sequence":41,"source_event_id":"01JEXAMPLEDECISIONEVENT","tenant_id":"tenant-a"}
```

```python
import json
from memory_fabric.causal_replay.types import DecisionRecord, parse_record, serialize_record

record = parse_record(DecisionRecord, json.loads(example_json))
assert parse_record(DecisionRecord, serialize_record(record)) == record
bad = json.loads(serialize_record(record))
bad["unrecognized"] = True
try:
    parse_record(DecisionRecord, bad)
except ValueError:
    pass  # invalid schema/input is refused
else:
    raise AssertionError("unknown record field was accepted")
```

Capture accepts 1–100 unique, non-empty evidence IDs and refuses event budgets
outside 1–100,000 or any historical snapshot exceeding its event budget. A
missing, private, withdrawn, or erased reference returns the same generic
`ERASED` refusal without IDs, counts, content, or lineage. A revoked credential
returns `UNAUTHORIZED`; callers must obtain a newly authorized session before
retrying. These failure statuses do not produce partial records.

The current replay runner supports `noop`, `suppress`, `replace`, `delay`,
`withhold`, and `swap_policy` for typed observations. It may
not change options, policy or simulator unless an explicit policy intervention
is included and separately labeled. Replay returns `EXACT` only when the
registered built-in deterministic updater and complete supported inputs
resolve and the factual fingerprint matches. Arbitrary simulator callbacks
are rejected. Otherwise it returns
`APPROXIMATE` or `NON_REPLAYABLE`; neither status can create a verified causal
claim.

## Local decision timeline

Build a display model with `build_timeline(states, proposals,
intervention_sequence=...)`, then render it with
`render_local_viewer(document)`. The result is one self-contained HTML string:
it includes no CDN, remote fonts, network calls, or server listener. It explains
which evidence and beliefs were present at each step, labels a hypothetical
intervention window, and states that proposals do not execute actions. Treat
the evidence rows as a local diagnostic view and apply the same current access
and erasure rules before exporting or sharing them.

## Local quickstart

From a fresh checkout, use the repository's Python environment and run:

```powershell
python -m unittest tests.test_cdm_types tests.test_cdm_capture tests.test_cdm_replay
python -m benchmarks.cdm_battery_world --seed 20261108
python -m benchmarks.cdm_trace_world --seed 20261108
```

These commands use the checked-out source and Python standard library. The
battery example is synthetic and does not connect to a physical device. For
the normal memory loop, see [How to use Memory Fabric](HOW_TO_USE_MEMORY_FABRIC.md).

## Stable refusal codes

`INVALID_INPUT`, `UNAUTHORIZED`, `ERASED`, `NON_REPLAYABLE`,
`POLICY_UNAVAILABLE`, `BUDGET_EXCEEDED`, `INTERVENTION_INVALID`,
`TRACE_INCOMPLETE`, `CERTIFICATE_INVALID`, `SIMULATOR_FORBIDDEN`.

Refusals do not disclose inaccessible IDs, former existence, content, counts or
lineage. Certificate JSON is canonical UTF-8 with sorted keys, finite numeric
values only, explicit schema version and SHA-256 digests. Certificate
verification checks the certificate payload digest; the separate replay
verifier recomputes each deterministic belief/proposal step before a trace is
treated as verified. Neither grants action authority.
Certificates record typed status, estimand, world semantics, and a minimality
claim. Physical counterfactual semantics are unsupported and do not verify as
exact. Minimality defaults to `none`; a sufficient-subset proof digest is a
commitment only. Inclusion-minimality and cardinality-minimum are not supported
until a separate verifier recomputes their proofs.

Verify a local full certificate artifact without a network service:

```powershell
python tools/verify_cdm_certificate.py path\to\certificate.json
```

The command prints only `VERIFIED` or `REFUSED`. A masked summary intentionally
omits commitments and cannot be used for full certificate verification.

## Migration

The CDM decision receipt is an additive event type in the existing append-only
event log; projections ignore it and no table migration is required. Replay
certificates and derived artifacts remain separate from authoritative
memory/action records. Existing stores open without CDM configuration.

Existing event logs remain readable because the new decision event is additive
and projections skip unknown event types. Existing clients can continue using
the regular Memory Fabric APIs unchanged. Consumers that opt into CDM should
parse only the current compatible schema major/minor and handle
`UNAUTHORIZED`, `ERASED`, `BUDGET_EXCEEDED`, `TRACE_INCOMPLETE`, and
`NON_REPLAYABLE` as whole-operation refusals; they must not retry with broader
IDs or infer which inaccessible reference failed.


## Combining interventions

`compose_interventions((first, second, ...))` validates every operation digest before replay. It refuses repeated evidence targets, multiple policy swaps, and a no-op combined with other operations because their ordering or meaning is ambiguous. Independent evidence targets can be combined in a batch and are applied only to the disposable trace. A refused batch performs no simulator replay; the source log and source observations remain unchanged.


## Source withholding

`withhold` requires an inclusive sequence interval and an evidence reference from a fresh `CaptureResult`. Use `replay_captured` so current tenant/principal access, erasure state, capture digest, and the exact observation-to-evidence mapping are rechecked before replay. Only the captured target observation is hidden, and only when its sequence falls inside the declared interval. Outside the interval it remains visible. Withholding is a disposable replay overlay and does not change the source log.


## Model sensitivity

A `sensitivity` intervention applies a frozen, provenance-labelled `SensitivityFixture` to one declared CPT entry. It does not remove, replace or rewrite observations and returns `intervention_kind="model_assumption_change"`; evidence operators return `evidence_change`. The model fixture is committed by digest, and unsupported node or parent assignments refuse. This is a sensitivity scenario, not evidence that the changed assumption is better calibrated.

## Intervention operator contract

| Operator | Preconditions | Hypothetical effect | Refusal / control |
|---|---|---|---|
| `noop` | No target or parameters | Same deterministic belief fingerprint | Non-empty parameters refuse; no-op regression equals the factual state |
| `suppress` | Target reference occurs exactly once in the explicit trace | Removes that observation from the disposable trace | Missing/ambiguous target refuses; source observation/log remain unchanged |
| `replace` | Target plus a typed, labelled `ReplacementFixture` with matching ID and sequence | Substitutes the fixture observation only in the overlay | Unlabelled, mismatched or absent fixture refuses; replace/suppress controls are tested |
| `delay` | Target and later non-negative sequence | Changes only hypothetical visibility order | Missing target or non-later sequence refuses |
| `withhold` | Fresh authorized capture and inclusive valid sequence interval | Masks only the captured target inside the interval | Erased/revoked evidence or invalid interval refuses; outside-window evidence stays visible |
| `swap_policy` | Explicit policy ID and no evidence target | Recomputes under a distinct policy identity | Missing ID or mixing policy parameters into evidence operations refuses |
| `sensitivity` | Frozen local `SensitivityFixture` for a declared CPT entry | Changes model assumptions while retaining evidence | Invalid node/parent assignment/digest refuses; labelled separately from evidence changes |
| batch | Individually digest-valid operations on independent targets | Applies operations to one immutable overlay | Duplicate targets, multiple policy swaps, or mixed sensitivity/no-op refuse before replay |

All operators are local hypothetical transformations. None writes to the Memory
Fabric event log, changes authorization, or grants action entitlement. Physical
world claims remain unsupported; the certificate verifier refuses the
`physical_counterfactual_unsupported` world semantics.


## Dependency frontier and downstream replay

`replay_frontier` returns the conservative sequential suffix beginning at the
earliest affected event. `dependency_frontier` instead returns the target and
its transitive dependents in trace order; a certified graph must declare every
event and only reference earlier events. If completeness is unknown, both
selectors retain the full trace.

`execute_dependency_frontier` accepts an exact factual execution and a
counterfactual trace where only the declared target changed or was suppressed.
With a complete dependency graph, it recomputes policy proposals for the
affected frontier and reuses only unaffected baseline proposals. It rebuilds
every prefix fingerprint and the final belief state from the full
counterfactual trace, so source provenance and trace identity are retained.
`consumed` reports the number of policy proposals recomputed. Unknown
completeness falls back to exhaustive replay. The caller must supply a
semantically complete dependency graph: a graph that omits an actual causal
link can reuse a stale proposal. The test suite compares frontier replay step
for step and fingerprint for fingerprint with exhaustive replay on seeded
fixtures, and verifies fallback and malformed-graph refusal. A certified
dependency adapter remains part of the correctness boundary; the executor
cannot infer domain causality from event IDs alone.

## Deterministic simulated environments

`DeterministicEnvironment` is a versioned, immutable state/action transition table. A changed hypothetical action selects its registered transition and generates a new simulated observation plus a digest-only `ToolObservation`; it never invokes a real tool or caller callback. The simulator ID, version, transition schema and input/output commitments are explicit. An unregistered state/action pair refuses instead of falling through to external execution.

When a changed action has dependent later observations, `continue_counterfactual` returns `UNDEFINED_CONTINUATION` if no simulator is supplied. With a registered deterministic environment it regenerates the dependent observation and binds the result to that simulator's version. Independent later observations do not require a simulated continuation.


The built-in `battery_sensor_environment()` is an illustrative synthetic cooling/diagnostics world. It is a finite Python transition table for tests and examples, not a physical battery model or hardware interface.

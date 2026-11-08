# Causal replay security boundary

CDM is experimental and simulation-only. The existing `ActionGate`, tenant
authorization, lifecycle policy, and append-only event log remain authoritative.

```text
Host / credential verifier
          |
          v
MemoryService.Session -- explicit IDs --> Current + historical authorizer
                                                   |
                                                   v
                                         bounded archival capture
                                         (commitments; no plaintext copy)
                                                   |
                                                   v
                                      disposable intervention overlay
                                                   |
                                                   v
                                  built-in deterministic data simulator
                                      (no callback/tool execution)
                                                   |
                           proposal trace --> diagnostic evaluator
                                  |                       |
                                  +--> independent verifier --> certificate
                                                                  |
                                                        no action entitlement
```

## Threats and current controls

| Threat | Current control | Evidence / remaining work |
|---|---|---|
| Unauthorized or cross-tenant historical lookup | Capture requires a `Session` bound to the same fabric, rechecks its credential before and after the read, and intersects snapshot visibility with current `fabric.use`. | `tests/test_cdm_capture.py::test_cross_tenant_capture_refuses_without_metadata`, `test_revoked_session_cannot_capture`; `tests/test_cdm_privacy.py::test_repeated_capture_after_revocation_never_returns_artifact`. |
| Erased plaintext reappears in a checkpoint | CDM stores a content digest only; capture and checkpoint verification check current erasure and refuse. | `tests/test_cdm_capture.py::test_capture_refuses_erased_content`, `tests/test_cdm_checkpoints.py`; no plaintext checkpoint is stored. |
| Evidence poisoning or contradictory-source confidence inflation | Same-origin duplicates count once; contradictory distinct sources remain visible but are excluded from conditioning absent a registered sensor model. | `tests/test_cdm_bayes.py::test_noop_irrelevant_and_same_origin_duplicate`, `test_conflicts_remain_in_trace_and_use_declared_first_source_rule`. |
| Prompt injection in evidence becomes executable policy | Unknown injected variables are refused; source-origin strings are inert metadata; evidence content is not passed to an LLM or command interpreter. | `tests/test_cdm_privacy.py::test_prompt_injection_cannot_become_an_undeclared_model_variable`, `test_injection_text_in_source_metadata_is_inert`, `test_hostile_text_cannot_become_a_typed_observation`. |
| Real tool/action executes during counterfactual | Replay accepts only a `DeterministicSimulator` data object and calls the package’s own update function; no callback/tool adapter is invoked. | `tests/test_cdm_bayes.py::test_arbitrary_callable_simulator_is_refused`; `tests/test_cdm_verifier.py::test_replay_certificate_cannot_execute_a_protected_tool`. |
| Forged or modified certificate | Strict fields, schema, digest formats, claims and certificate digest are verified; a separate verifier recomputes replay and minimality claims. | Tamper and recomputation cases in `tests/test_cdm_replay.py`, `tests/test_cdm_verifier.py`; measured attack-rate matrix is tracked under CDM-120. |
| Evidence inference or hidden-ID enumeration | Missing/private/erased historical rows collapse to a generic unavailable error and no row count is returned. | `tests/test_cdm_capture.py::test_cross_tenant_capture_refuses_without_metadata`, private and erased cases; full timing side-channel review remains open. |
| Historical authorization is confused with current action authority | Capture is archival-only; certificate has `action_entitlement=False`; no replay result grants an action. | `tests/test_cdm_verifier.py::test_replay_certificate_cannot_execute_a_protected_tool`; execution callback remains untouched despite a tool grant. |
| Decision options are changed after the decision | Decision is appended to the immutable event log as a digest-only receipt; capture verifies event ID, sequence, session agent/tenant, policy identity and complete record digest. Option additions require an explicit different-policy intervention. | `tests/test_cdm_capture.py::test_original_options_and_constraints_bind_to_authorized_capture`; tampered option sets/event IDs fail and receipt payload contains no option or constraint text. |
| Unknown or substituted policy implementation is replayed as exact | Recorded replay resolves the policy ID and digest against the current local implementation and parameters; missing source or any digest mismatch refuses. | `tests/test_cdm_replay.py::test_recorded_policy_digest_must_resolve_to_exact_local_implementation`. |
| Seed-only RNG or opaque tool continuation is certified exact | Decision records distinguish not-applicable deterministic RNG, complete Python RNG snapshots and missing RNG state; tool/environment output carries an explicit determinism class. Recorded replay refuses missing RNG or any tool continuation without a pure local handler. | `tests/test_cdm_replay.py::test_rng_snapshot_roundtrips_full_state_and_internal_position`, `test_recorded_policy_digest_must_resolve_to_exact_local_implementation`; `tests/test_cdm_types.py::test_tool_observation_determinism_classes_are_closed`. |
| Evaluator output mutates trust or authority | The evaluator accepts a typed observed outcome and only returns a diagnostic assessment; calibration takes immutable inputs and reports metrics. | Evaluator module has no fabric/session/action dependency; full stateful compromised-agent matrix remains open. |

The replay implementation is not an OS sandbox. Its current scope is the
finite Bayesian engine and typed observations. Do not register untrusted
extensions or describe this package as a security boundary against malicious
in-process Python code.

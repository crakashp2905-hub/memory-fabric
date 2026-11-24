# Vega-U semantic advisor: threat model

Each threat has a control, a test, and a residual risk. Tests are in
`tests/test_vega_cdm_security.py` unless named otherwise.

| Threat | Control | Test | Residual risk |
|---|---|---|---|
| Instructions inside evidence steer the advisor into granting or approving | Questions have closed, host-defined options; an answer outside them is `INVALID`; no answer reaches a grant | `Injection::test_instructions_inside_evidence_stay_data` | A model can still be wrong inside the allowed options (the measured unsafe misreadings) |
| Option text redefines authorization or score direction | Labels must be identifiers; boolean criteria are exactly true/false; the host writes every option | `Injection::test_option_text_and_labels_are_host_defined_and_closed` | Instruction wording is still host text a careless caller could write badly |
| Advisor names unauthorized, erased or foreign evidence | Packets come only from authorized retrieval and are rechecked; interventions must target a readable, exposed packet | `Injection::test_a_model_cannot_name_an_unauthorized_or_erased_target` | None known in the tested paths |
| Copies through summaries look independent | Source roots come from lineage, never from the model | `Injection::test_copies_forwarded_through_summaries_keep_their_origin` | Copies made outside the store, with no lineage, are not detected |
| Cross-tenant or cross-principal cache reuse | Cache keys bind tenant, principal, bundle digest, model and policy | `Injection::test_cache_keys_never_collide_across_tenants_or_principals` | Timing differences between cache hit and miss are not equalised |
| Evaluator truth or future data in a request | Sealed fields are refused in packets; beliefs use evidence known by the decision time | `Injection::test_sealed_truth_and_future_data_never_reach_a_request` | Truth leaked into free text by a careless fixture author would not be caught by field names |
| Malformed, non-finite or unnormalised outputs | Strict parser; anything it would have to guess is `INVALID` | `tests/test_vega_u_adapter.py::FailClosed::test_malformed_outputs_become_invalid_never_confident` | None known |
| Spoofed server, substituted checkpoint, remote endpoint | Loopback only, proxies bypassed, handshake pins runtime, reader and engine digest | `Spoofing::test_a_replayed_or_substituted_server_identity_is_refused`, adapter `FailClosed` | A local process can lie about its digest |
| Code, files or shell smuggled through proposals | Closed intervention vocabulary; extra response keys are ignored, never executed | `Spoofing::test_proposals_cannot_carry_code_files_or_shell` | None known |
| Governance regresses | Semantic modules do not import governance writers; the existing governance suites run unchanged in CI | `GovernanceUnchanged`, plus the full suite | A future change could add an import; the test would catch it |
| Inference outage or slowness hangs an actor | Deadline, bounded retries, circuit breaker, deterministic fallback | adapter `FailClosed::test_timeouts_errors_and_budgets_fall_back_and_the_breaker_opens` | The deterministic fallback may abstain more |

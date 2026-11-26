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

## Boundaries added by the feature-freeze plan

| Threat | Control | Test | Residual |
|---|---|---|---|
| A model answer (the advisor's or the planner's own choice) settles contested readings without cooling | Under `CONTESTED`, a decision the deterministic reader did not support must still be a registered response | `tests/test_omission_safety.py::ModelSettledContest`, `tests/test_vega_next_study.py::PlannerContest` | A wrong deterministic doubt reading would still permit recalibration |
| A stale or unbound human approval authorizes a modified action | Approvals may expire; an action with a request needs an approval bound to it | `tests/test_action_fence_typed.py::ApprovalBinding`, `tests/test_authority.py::ExactActionGrants` | Approvals recorded without a binding by older releases still cover requestless calls |
| A reused idempotency key reports a different action as done | Every first call binds its key, with or without a request | `tests/test_action_fence_typed.py::IdempotencyBinding` | Keys first used by older releases carry no binding |
| A model or replay worker forks, allocates or spins without bound | `outcome_typed.limited_process`: CPU, address-space and process-count limits; a root parent drops the child to `nobody`; a refused limit means not run | `tests/test_vega_next_security.py::Isolation` | No syscall filter (seccomp) and no network namespace |
| Punctuated or spelled sensor names make two instruments one claim (fake corroboration or contradiction) | Claim identity v2 normalises designators | `tests/test_sensor_entity_claims.py::HeldOutIdentities` | Designators outside the registered noun list are not recognised |
| A statement negated as a whole is read as asserted | Whole-statement negation makes the reading UNKNOWN | `tests/test_semantic_quantities.py::AnnotatedFixtures` | Negation phrasings outside the list stay unrecognised and read literally |

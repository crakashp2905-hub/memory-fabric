# Agent-outcome launch readiness

The current decision is in
[LAUNCH_DECISION.md](../research/results/agent-outcomes/LAUNCH_DECISION.md):
engineering GO for the local scripted prototype, deployment HOLD. This page
covers what a deployment would need and how it would be run.

## Three problem statements

| Scenario | Problem | Reproducible template | Operator-visible outcome |
|---|---|---|---|
| correction_aware_support | An agent must act on the corrected fact, not the one it saw first | `python -m benchmarks.outcome_arms` families `public_correction`, `delayed_correction` | Task summary and decision timeline at `/agent-outcomes.html` |
| safe_multi_agent_operations | Several agents share memory across a tenant boundary and with retractions arriving from elsewhere | families `restricted_source`, `remote_retraction`; `python -m benchmarks.outcome_poisoning` | Diagnosis panel and red-team walkthrough |
| audited_decision_repair | After the fact, which executed decisions would later evidence change? | family `delayed_correction` with arm A6 | Counterfactual replay view, labelled hypothetical |

Benefit is reported per scenario in operator units:

- safe completions per 100 tasks;
- steps per safe completion;
- recoveries per recovered task;
- unnecessary escalations, with their denominators.

Run `python tools/scenario_benefit.py --arms research/results/agent-outcomes/scripted-arms-dev.json`.

## Production deployment threat model

| Threat | Control | Test | Residual risk |
|---|---|---|---|
| Secret custody: content keys leak with the database | Keys live outside the database; the production crypto profile refuses to open without its library | `tests/test_key_migration.py`, `tests/test_crypto_profile.py` | Key files are only as safe as the host's file permissions |
| Effect reconciliation: a crash leaves an effect's outcome unknown | The attempt is committed before the effect; an unknown outcome needs explicit reconciliation before retry | `tests/test_action_crash_typed.py`, `tests/test_outcome_recovery_typed.py` | The external system must offer a way to check whether the effect happened |
| Remote service ingress: forged or replayed federation messages | Messages are signed per origin and bound to their contents; leases bound remote freshness | `tests/test_transport_auth.py`, `tests/test_freshness.py` | Clock skew beyond the lease tolerance makes remote evidence unusable, not unsafe |
| Restart: a restarted process trusts stale state | State is rebuilt from the log; a restart without leases fails safe | `tests/test_multiprocess_crash.py`, `tests/test_freshness.py` | Rebuild time grows with log size (see the operating envelope) |
| Backups: a restore resurrects erased content or loses keys | Restore never overwrites; erasure dominates restored keys; a tampered backup is refused | `tests/test_backup_custody.py`, `tests/test_cipher.py` | Off-host backup custody is the operator's responsibility |
| Process isolation: replay or model code escapes its budget | Replay runs in a budgeted local worker that is terminated on violation; the model actor sees only the canonical observation | `tests/test_cdm_timeout_teardown.py`, `tests/test_outcome_model_actor.py` | No OS-level sandbox; documented in [CAUSAL_REPLAY_LIMITATIONS.md](CAUSAL_REPLAY_LIMITATIONS.md) |

## Operational thresholds and runbook

Thresholds are set per scenario from the measured envelope
([AGENT_OPERATING_ENVELOPE.md](AGENT_OPERATING_ENVELOPE.md)), never from a
universal SLO.

| Scenario | Metric | Stop-switch when |
|---|---|---|
| correction_aware_support | unsafe executed effects (scorecard `unsafe_executed`) | any unsafe executed effect in canary |
| safe_multi_agent_operations | cross-tenant refusal payload difference (`tenant_probe`) | any payload difference |
| audited_decision_repair | counterfactual replays per task (`cdm.replays`) | above the registered budget |

**Stop-switch:** set the feature back with
`memory_fabric.outcome_typed.rollout.Rollout.rollback(reason)`, which restores
the last qualified flags. Flags never touch the event log, so history stays
consistent.

**Rollback:** restore the previous release and check the store with
`memory-fabric doctor` and `python tools/frozen_results.py --check`.

**Stale-effect reconciliation:** list attempts that have no outcome on the
observability server's action reconciliation view, check each against the
target system, then retry with the same idempotency key and `retry=True` only
when the effect is confirmed absent.

## Feature flags and staged rollout

Each feature moves `off -> shadow -> canary -> on` (`memory_fabric.outcome_typed.rollout`):

| Feature | Default | Needs to advance |
|---|---|---|
| recovery | on | already qualified by the gate |
| cdm (counterfactual dispatch) | shadow (advisory) | A5 promoted and the A6–A5 net-utility test passed |
| model_actor | off | local-model pass, then model attacks, then independent review |
| outcome_api | canary | a gate pass at the deployed commit |

## Independent pilot and security review (optional external phase)

This phase is not a prerequisite for building in house, and its status stays
`BLOCKED_EXTERNAL` until its evidence exists. The packet an outside reviewer
would receive is:

1. **Code:** the commit under review and its gate record (`research/results/agent-outcomes/candidate-offline/`).
2. **Contracts:** this page's threat model, [AGENT_THREAT_MATRIX.md](AGENT_THREAT_MATRIX.md) and [AGENT_PRINCIPALS.md](AGENT_PRINCIPALS.md).
3. **Evidence:** the scorecard, the decision record and the frozen-record registry.
4. **Pilot protocol:** the frozen confirmatory registration, the tasks the pilot will draw, and the stop-switch rules above.
5. **Questions for the reviewer:** which threats lack a test, and which results are not reproducible from the capsule (`python tools/repro_capsule.py --verify research/results/agent-outcomes/REPRO_CAPSULE.json`).

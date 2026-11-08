# ADR-CDM-001: Isolated counterfactual replay package

Status: accepted for experimental implementation. Date: 2026-11-08.

## Decision

Implement CDM as an additive `memory_fabric.causal_replay` package with pure
typed records, explicit policy/updater registrations, and disposable simulation
overlays. No existing stable method changes and no new dependency is added.

## Reuse

- `history_query.query` remains the authority for bounded historical explicit-ID
  reads and current/historical permission intersection.
- `decision_models.DecisionContext` and `DecisionProposal` represent proposals;
  neither may execute or authorize actions.
- `influence.edges/downstream` supplies candidate-pruning only.
- `dependence.decisions_depending_on` continues to classify certificate
  sufficiency; a CDM replay callback can answer the separate choice-change
  question.
- Event log, projection, source roots, erasure and `ActionGate` remain
  authoritative and unchanged.

New types are necessary because these APIs do not represent a typed belief
snapshot, an intervention overlay, replay fidelity state, or a replay
certificate. Branch commits are not used as the default sandbox because they
write persistent candidate events.

## Consequences

The first implementation targets deterministic discrete simulators. Opaque
model/tool continuations are non-replayable unless an explicit, limited replay
contract exists. The replay runner uses data-only deterministic simulator
configurations and accepts no caller-provided tool-handler callbacks.
Certificates carry no action entitlement. Historical content is never
materialized without current authorization, and is never recovered after
erasure.

# Agent-outcome research report

Status: **development**. No learned agent, confirmatory study or independent
review stands behind any finding here. Each finding names its claim tier and
links the evidence for that tier:

- **CONTRACT**: a test shows the behaviour.
- **SCRIPTED**: measured with scripted agents on designed worlds.
- **LOCAL_MODEL**: measured with a local model.
- **CONFIRMATORY**: a frozen, preregistered, held-out study.
- **INDEPENDENT**: replicated or reviewed by an outside party.

The last three tiers have no findings; they are listed as NOT_RUN below, not
left out.

## Null and negative results first

| # | Result | Tier | Evidence |
|---|---|---|---|
| N1 | Phase A was killed: with a real local model, governed memory lost to an ungoverned vector store, and the governance mechanism caused the loss | LOCAL_MODEL (historical) | [phase-a-real-agent-benchmark.md](../research/results/phase-a-real-agent-benchmark.md) |
| N2 | The R5 v3 counterfactual architecture-superiority interval crosses its frozen margin, so superiority is not supported | CONFIRMATORY (historical, CDM) | [R5 v3 confirmatory report](../research/results/cdm/architecture-superiority-r5v3/confirmatory/report.md) |
| N3 | Counterfactual dispatch (A6) adds no outcome over A5; flips earn nothing and net utility is negative, so A6 stays advisory | SCRIPTED | [SCRIPTED_ARMS_DEV.md](../research/results/agent-outcomes/SCRIPTED_ARMS_DEV.md) |
| N4 | On the current-value task, fair retrieval baselines tie governed retrieval on accuracy; governance saves context, not accuracy | SCRIPTED | [DEV_RESULTS_W05_W11.md](../research/results/agent-outcomes/DEV_RESULTS_W05_W11.md) |
| N5 | Governance helps one of five designed families against an equally capable recovery baseline (A5−A3 comes only from `restricted_source`) | SCRIPTED | [SCRIPTED_ARMS_DEV.md](../research/results/agent-outcomes/SCRIPTED_ARMS_DEV.md) |
| N6 | Planner errors hurt governed and pooled memory equally; governance does not correct a wrong decision on correct evidence | SCRIPTED | [scripted-ablation-dev.json](../research/results/agent-outcomes/scripted-ablation-dev.json) (`orthogonal`) |
| N7 | More process workers did not help on the measured host; eight workers were slower than one | SCRIPTED | [performance-dev.json](../research/results/agent-outcomes/performance-dev.json) |
| N8 | A permitted record worded unlike the query is missed and reported as not available (a false denial) | SCRIPTED | [diagnosis-dev.json](../research/results/agent-outcomes/diagnosis-dev.json) |
| N9 | Harder worlds (readings from 2 or 8 other instruments) make governed and pooled memory abstain alike; governance does not help disambiguate sources | SCRIPTED | [scripted-ablation-dev.json](../research/results/agent-outcomes/scripted-ablation-dev.json) (`orthogonal.world_difficulty_distractor_instruments`) |

## Findings

| # | Finding | Tier | Evidence |
|---|---|---|---|
| F1 | Access control (tenant scoping plus the action gate) is the only mechanism that separates A5 from A3 among the original five families | SCRIPTED | [SCRIPTED_ARMS_DEV.md](../research/results/agent-outcomes/SCRIPTED_ARMS_DEV.md) |
| F2 | When a correction does not say it is one, pooled memory with recheck abstains on the contradiction, while governed memory completes because the correction withdraws what it corrects | SCRIPTED | [scripted-ablation-dev.json](../research/results/agent-outcomes/scripted-ablation-dev.json) (`orthogonal.evidence_quality`) |
| F3 | A correction landing between retrieval and proposal is caught only by verification at action time | SCRIPTED | [scripted-ablation-dev.json](../research/results/agent-outcomes/scripted-ablation-dev.json) (`orthogonal.correction_timing_tick`) |
| F4 | Copies never amplify corroboration: up to 50 colluders stay one source root | SCRIPTED | [poisoning-dev.json](../research/results/agent-outcomes/poisoning-dev.json) |
| F5 | Every effect path (gate, tools, MCP/UTCP/Code Mode runtime) allows and refuses the same actions | CONTRACT | `tests/test_effect_transport_parity.py` |
| F6 | Foreign and missing memory ids get identical visible refusals | CONTRACT | `tests/test_agent_security_fixtures.py` |
| F7 | Valid-time-aware answering beats timeless-contradiction and latest-known policies on temporal worlds | SCRIPTED | [extra-worlds-dev.json](../research/results/agent-outcomes/extra-worlds-dev.json) |

LOCAL_MODEL: NOT_RUN for this program (no model checkpoint was available).
CONFIRMATORY: NOT_RUN (registrations
[v2](../research/prereg/agent-outcome-confirmatory-v2.json) and
[A6–A5](../research/prereg/agent-outcome-cdm-a6-v1.json) are blocked drafts).
INDEPENDENT: NOT_RUN.

## Related work: what is existing and what differs

These are mechanism categories, not claims about any specific system. The
first-party baselines in this repository are written from public descriptions
of these ideas and labelled as such
([retrieval baselines](../benchmarks/outcome_retrieval_baselines.py)); they are
not reproductions.

| Mechanism | Existing baseline category | Overlap | What is actually different here |
|---|---|---|---|
| Exact dependence (which decision used which evidence version) | Provenance tracking, data lineage | Records what was derived from what | Dependence is checked at action time, and it decides which past decisions are replayed |
| Versioned correction | Event sourcing, bitemporal databases | Append-only history, valid and known time | A correction withdraws what it corrects, and the withdrawal propagates to other stores with acknowledgements |
| Replay certificates | Deterministic replay, record and replay debugging | Re-running a recorded computation | A certificate is checked by an independent verifier and can never authorize an effect |
| Independent-root corroboration | Source deduplication, citation counting | Counting distinct sources | Copies made by agents who were shown a claim count as the same root |
| Action gate with exact grants | Capability security, idempotency keys | Least privilege, at-most-once effects | The grant is bound to the exact request and to evidence re-verified in the same transaction |
| Counterfactual dispatch | Leave-one-out and Shapley attribution | Asking what would change without an input | Dependence first: independent decisions are never replayed, and flips earn no credit |

## How to test the thesis

The registered thesis is: governed correction plus recovery improves safe
terminal utility over pooled memory plus recovery at equal budget. The primary
contrast is A5−A3 in
[agent-outcome-confirmatory-v2.json](../research/prereg/agent-outcome-confirmatory-v2.json).
Uncertainty follows `memeval`, with the seed cluster as the unit. A registration
whose effect exceeds the measured headroom, or that is underpowered, is refused
before any run.

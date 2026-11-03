# Next master checklist execution ledger

Baseline audited 2026-11-01. This ledger distinguishes repository completion
from independent or external qualification. `DONE` means reproducible evidence
exists; `PARTIAL` means some acceptance evidence remains; `EXTERNAL` requires
people, accounts, licensed resources or physical infrastructure outside this
repository. External items are never converted to DONE by internal tests.

## Pinned state

| Subject | Exact state |
|---|---|
| `main` baseline | `d4fd174ac9056865c8b73abd857fa681daa6a0d7` |
| PR #30 candidate | `12c612ea37980f92d206fe2b343b217603d1b3cc` |
| PR #30 | OPEN and mergeable; not a release |
| Candidate CI | 33/33 jobs passed, run `41319107155` |
| Release decision | **NO-GO** until external and operational gates close |

## Gate status

| Gate | State | Evidence / blocker |
|---|---|---|
| G0 baseline validity | PARTIAL | B01–B05 and B09 reproduced; HTTP, LongMemEval and local Windows adversarial-runner qualification remain |
| G1 false withholding | DONE in deterministic TeamWorld scope | Held-out verified-observation result: 89.8% success, 3.6% withholding, zero stale actions; scope limitation retained |
| G2 real-agent value | OPEN | Hosted/local real-model matched study across model families is not replaced by deterministic TeamWorld |
| G3 performance | **NO-GO on SQLite tier** | Repeated 1/5/10/25/50-client curve: 5,460/5,460 correct, throughput saturated at 4.3–4.8 ops/s and 50-client mean p99 was 24.2 s. PostgreSQL and physical-host evidence remain. |
| G4 security | EXTERNAL | Independent second model family and human reviewer are required; internal tests are not independence |
| G5 integration | PARTIAL | MCP/UTCP/Code Mode contracts and per-effect gating exist; matched external transport study remains |
| G6 research | OPEN | Positive internal held-out result exists; independent replication and novelty/ablation requirements remain |
| G7 pilot | EXTERNAL | Requires a supervised customer or design partner |
| G8 release | **NO-GO** | Owner approval, G2–G7 and exact candidate release evidence remain |

## Checklist coverage

| IDs | State | Evidence / exact remaining work |
|---|---|---|
| B01–B05 | DONE | `grand-50-agent-baseline-reproduction-v2.*`; exact SHA, source hashes, machine, per-seed values, CIs and denominators |
| B06 | DONE, threshold FAIL | Clean candidate: 1,000/1,000, all families, 29.1 ops/s, p99 3,292 ms; `master-checklist-http-50.*`. Historical machine-sensitive values not reproduced exactly |
| B07 | DONE, threshold FAIL | Clean exact reproduction: lexical 73.85%, hybrid 69.17%; dataset SHA and limitations in `longmemeval-s100-reproduction-v2.*` |
| B08 | DONE | `tools/adversarial_gate.py --temp-dir PATH`; unchanged 21-family gate passed on Windows outside the loopback-restricted sandbox |
| B09 | DONE | Candidate CI run `41319107155`, all 33 jobs passed on exact SHA |
| B10–B11 | DONE for current checklist claims | Machine-validated `research/claims.json` generates `research/results/CLAIMS_LEDGER.*`; every registered claim binds evidence hash, commit, scope and limitation. Public TeamWorld prose now separates the historical result from the current deterministic-agent baseline. |
| B12 | DONE for current failed gates | TeamWorld emits ten deterministic failures per arm with seed/task replay coordinates and causal flags; HTTP retains per-operation latency failures; LongMemEval retains type-level results. |
| E01–E03, E07–E10, E14–E15, E17 | DONE in current APIs | Typed lifecycle/reason codes, answerability, action requirements, recovery guidance, independence and correction regressions |
| E04–E06, E11–E13, E16, E18 | PARTIAL | Aggregate attribution and calibration studies exist; requested multidimensional/worst-agent/ablation report remains |
| A01–A03, A10–A13, A15 | PARTIAL | TeamWorld attribution, matched arms and deterministic routing exist; full trace/failure corpus and category reports remain |
| A04–A09, A14, A16 | OPEN/GATED | Real-model families, long-horizon held-out split and perturbation study require registered model runs and budget |
| P01–P02, P04, P15 | DONE for single-host SQLite | Warmed, three-trial 1/5/10/25/50-client capacity curve with per-operation p50/p95/p99, hardware, operation mix and CIs in `master-checklist-http-capacity-v1.*`; threshold fails. |
| P03, P05–P07, P09–P11, P14 | PARTIAL | Catch-up, idempotency and upgrade tests exist; stage-level DB/serialization/policy profiling and PostgreSQL comparison remain. |
| P08, P12–P13, P15–P16 | OPEN/EXTERNAL | 1M scale, three physical hosts, partitions and representative 24–72h soak need deployment resources |
| S01–S03, S05–S17 | PARTIAL | Extensive internal adversarial, race, checkpoint and crypto evidence exists; isolated independent audit and consolidated remediation register remain |
| S04, S18 | EXTERNAL | Human reviewer and independently scoped residual-risk report required |
| D01–D12 | PARTIAL | Decision-model and dependency components/benchmarks exist; a versioned public DecisionRecord/timeline qualification remains |
| M01–M04, M08, M12 | DONE | Typed optional router with deterministic action boundary |
| M05–M07, M09–M11 | GATED | Laya/Jev/checkpoints, compute and registered multi-model data required |
| U01–U05, U07–U10 | DONE | Pinned UTCP subset, canonical descriptors, literal Code Mode sandbox, ActionGate per call, receipts/idempotency |
| U06, U11–U12 | PARTIAL | Local contract tests exist; matched external transports and expanded isolated red team remain |
| R01–R08, R13–R16, R21–R23 | PARTIAL | Registrations and several held-out synthetic studies exist; requested unified studies/ablations remain |
| R09–R12, R17–R20 | OPEN | Procedure learning and counterfactual pruning require fresh registrations and implementations |
| R24 | EXTERNAL | Separate physical machines and adversarial network schedules required |
| X01–X10, X13 | PARTIAL | Demo, Control Center, runbooks, deployment modes, SLOs, install matrix and comparison scaffolding exist; product qualification remains |
| X11–X12, X14–X15 | EXTERNAL/GATED | Customer pilot, product decisions, independent review and owner release approval required |
| Q01–Q06, Q08 | PARTIAL | Manifests, seeded runners, held-out splits, statistics, negative results and containers exist; one immutable runner remains to unify |
| Q07, Q09–Q10 | EXTERNAL/GATED | Blinded adjudicators, independent reproduction and publication decision require people/budget |

## External action register

1. Appoint and fund an independent human security reviewer for S04/G4.
2. Provide three independently clocked physical hosts for P12/R24.
3. Authorize model/checkpoint/API budgets and dataset licences for A04/M05.
4. Recruit a supervised pilot partner for X11/G7.
5. Configure package-index ownership and approve publication only after G8.

Until those actions occur, “complete all” means all independently executable
repository work is driven to evidence while these blockers stay explicit—not
that external assurance is simulated or claimed.

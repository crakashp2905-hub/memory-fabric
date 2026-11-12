# Documentation

**New here? Three steps, in order:**

1. `memory-fabric tour` â€” the idea in sixty seconds, in your terminal.
2. [QUICKSTART.md](QUICKSTART.md) â€” ten minutes with your own store.
3. [Any agent, any model](guides/any-agent-any-model.md): connect your tool and pick your
   model in two commands. Or a guide for your stack: [Claude Code and Desktop](guides/claude.md) Â·
   [LangGraph](guides/langgraph.md) Â· [OpenAI Agents SDK](guides/openai-agents.md) Â·
   [CrewAI](guides/crewai.md).

Then [CONCEPTS.md](CONCEPTS.md) when you want the why, and
[LIMITATIONS.md](LIMITATIONS.md) before you rely on it. Everything else
below is reference: you do not need it to start.

Every document in the repository, by what you are trying to do.
`tests/test_doc_index.py` fails if a document here is missing from this page.

## Getting started

| document | for |
|---|---|
| [../README.md](../README.md) | What it is, why, and a first example |
| [QUICKSTART.md](QUICKSTART.md) | Ten minutes: install, store, retrieve, inspect, correct, verify |
| [HOW_TO_USE_MEMORY_FABRIC.md](HOW_TO_USE_MEMORY_FABRIC.md) | A practical memory loop, model/agent setup, correction, and next steps |
| [CONCEPTS.md](CONCEPTS.md) | The ideas: memories, the log, lifecycle, scope, authority, correction |
| [COOKBOOK.md](COOKBOOK.md) | Task-sized recipes, each run by a test |
| [FAQ.md](FAQ.md) | Common questions, short answers |
| [PIPELINE.md](PIPELINE.md) | One memory from write to erasure, with what is and is not measured |
| [../examples/README.md](../examples/README.md) | Runnable examples |

## Reference

| document | for |
|---|---|
| [API.md](API.md) | The Python API, generated from the code |
| [DECISION_RECORD_SCHEMA.md](DECISION_RECORD_SCHEMA.md) | Typed decisions, evidence links, and correction impact queries |
| [CLI.md](CLI.md) | Every command and option, generated from the parser |
| [RETRIEVAL.md](RETRIEVAL.md) | Getting the best retrieval: trained embedders, rerankers, one line |
| [INTEGRATIONS.md](INTEGRATIONS.md) | MCP, HTTP, SDK, LangChain, Claude, Ollama, PostgreSQL |
| [PROTOCOL.md](PROTOCOL.md) | The federation protocol, v1 ([schemas](protocol/)) |
| [../SPEC.md](../SPEC.md) | The memory schema and event types, by version |
| [RELEVANCE_SPEC.md](RELEVANCE_SPEC.md) | The relevance contract |
| [DATA_ACCESS.md](DATA_ACCESS.md) | Every public way to reach a memory, and what each enforces |
| [../ARCHITECTURE.md](../ARCHITECTURE.md) | The design |

## Operating

| document | for |
|---|---|
| [../DEPLOYMENT.md](../DEPLOYMENT.md) | Serving, capacity as measured, upgrades |
| [OPERATIONS.md](OPERATIONS.md) | Day-two operations, incidents, background maintenance |
| [HEALTH_LEVELS.md](HEALTH_LEVELS.md) | Operator health levels and fail-closed meanings |
| [INCIDENT_REPLAY.md](INCIDENT_REPLAY.md) | Verify and replay redacted incident explanations offline |
| [RESOURCE_BUDGETS.md](RESOURCE_BUDGETS.md) | Configure retention, request, memory, and worker budgets |
| [RUNBOOKS.md](RUNBOOKS.md) | Step by step: leaked credentials, key rotation, poisoning, restore |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Every error message and what to do |
| [MIGRATION.md](MIGRATION.md) | Moving between versions, and moving in from elsewhere |
| [SCALE.md](SCALE.md) | How many agents, how far federated, what carries between sessions |
| [PILOT_KIT.md](PILOT_KIT.md) | Try it with your own agents and send back only the numbers |
| [PILOT_INVITE.md](PILOT_INVITE.md) | A one-page invitation to send a team you would like to pilot with |
| [REFERENCE_DEPLOYMENT.md](REFERENCE_DEPLOYMENT.md) | Two federated stores in five minutes |
| [CAUSAL_REPLAY_API.md](CAUSAL_REPLAY_API.md) | Experimental local replay contracts and examples |
| [schemas/cdm-belief-state-v1.json](schemas/cdm-belief-state-v1.json) | Generated versioned belief-state schema |
| [CAUSAL_REPLAY_LIMITATIONS.md](CAUSAL_REPLAY_LIMITATIONS.md) | Replay evidence limits and current gaps |
| [CAUSAL_REPLAY_SECURITY.md](CAUSAL_REPLAY_SECURITY.md) | CDM trust boundary, threats and controls |
| [COUNTERFACTUAL_DECISION_MEMORY.md](COUNTERFACTUAL_DECISION_MEMORY.md) | CDM scope, architecture, execution log and qualification status |
| [CDM_TASK_LEDGER.md](CDM_TASK_LEDGER.md) | Completion evidence against the 240-task CDM master plan |
| [CDM_EXECUTION_SCHEDULE.md](CDM_EXECUTION_SCHEDULE.md) | Dependency-ordered work queue and checkpoint rule |
| [CDM_CORRECTION_COMPARISON.md](CDM_CORRECTION_COMPARISON.md) | Correction review strategy comparison |
| [CDM_FEDERATED_PROVENANCE.md](CDM_FEDERATED_PROVENANCE.md) | Provenance across federated stores |
| [CDM_INTERNAL_GO_NO_GO.md](CDM_INTERNAL_GO_NO_GO.md) | Internal evidence-based GO/NO-GO criteria |
| [CDM_INVALIDATION_CLASSIFICATION.md](CDM_INVALIDATION_CLASSIFICATION.md) | Replay cache invalidation classes |
| [CDM_KNOWN_FINDINGS.md](CDM_KNOWN_FINDINGS.md) | Findings and limitations from the local work |
| [CDM_MISSING_REMOTE_EVIDENCE.md](CDM_MISSING_REMOTE_EVIDENCE.md) | Evidence gaps requiring remote validation |
| [CDM_MIXED_VERSION_FEDERATION.md](CDM_MIXED_VERSION_FEDERATION.md) | Mixed-version federation behavior |
| [CDM_REEVALUATION_CLASSIFICATION.md](CDM_REEVALUATION_CLASSIFICATION.md) | Re-evaluation and replay result classes |
| [CDM_TEMPFILE_POLICY.md](CDM_TEMPFILE_POLICY.md) | Temporary artifact storage policy |
| [CDM_SIDECHANNEL_AUDIT.md](CDM_SIDECHANNEL_AUDIT.md) | Capture lineage, timing, and checkpoint-cache review |

## Trust and security

| document | for |
|---|---|
| [../SECURITY.md](../SECURITY.md) | The threat model, T1â€“T12, and how to report a vulnerability |
| [SAFETY_AND_SECURITY.md](SAFETY_AND_SECURITY.md) | The safety model |
| [LIMITATIONS.md](LIMITATIONS.md) | What it does not do |
| [CRYPTOGRAPHY.md](CRYPTOGRAPHY.md) | Every cryptographic and key-management decision, written for review |
| [../STABILITY.md](../STABILITY.md) | What is stable, beta and experimental; what is tested |
| [HARDENING_STATUS.md](HARDENING_STATUS.md) | The owner's hardening lists, item by item, with evidence |
| [SAFETY_ROADMAP_COVERAGE.md](SAFETY_ROADMAP_COVERAGE.md) | The AI-safety roadmap, item by item |
| [SECURITY_REVIEW.md](SECURITY_REVIEW.md) | The internal security review and its findings |
| [DECISION_MODELS_AND_UTCP.md](DECISION_MODELS_AND_UTCP.md) | Typed decisions, System 1 escalation, UTCP, and governed Code Mode |
| [DEVELOPMENT_ROADMAP_2026Q4.md](DEVELOPMENT_ROADMAP_2026Q4.md) | Evidence ledger for the 2026-10-31 development and research roadmap |
| [SECURITY_TEST_PLAN.md](SECURITY_TEST_PLAN.md) | How security properties are tested |
| [INDEPENDENT_EVALUATION.md](INDEPENDENT_EVALUATION.md) | What an independent reviewer would need, and what has not happened |
| [INVARIANTS.md](INVARIANTS.md) | Each integrity invariant and the test that holds it |
| [ENGINEERING_RESEARCH_CHECKLIST.md](ENGINEERING_RESEARCH_CHECKLIST.md) | Engineering and research acceptance ledger, including external gates |
| [AUDIT.md](AUDIT.md) | Implementation against the spec |
| [VALIDATION.md](VALIDATION.md) | What was run and what it showed |
| [STATUS_AT_HEAD.md](STATUS_AT_HEAD.md) | Versions, tiers, skipped tests and contradictions, generated from the tree |
| [KNOWN_GAPS.md](KNOWN_GAPS.md) | What the masterplan asks for that is not done |
| [RELEASE_READINESS.md](RELEASE_READINESS.md) | Hard blockers and the definition of done, checked |

## Releases

| document | for |
|---|---|
| [../CHANGELOG.md](../CHANGELOG.md) | Every change |
| [RELEASE_NOTES_0.13.0.md](RELEASE_NOTES_0.13.0.md) | 0.13.0 qualification baseline (untagged, unpublished) |
| [RELEASE_NOTES_0.12.0.md](RELEASE_NOTES_0.12.0.md) | 0.12.0, in qualification |
| [RELEASE_NOTES_0.11.0.md](RELEASE_NOTES_0.11.0.md) | 0.11.0 |
| [RELEASE_EVALUATION.md](RELEASE_EVALUATION.md) | The release gate's evidence, per release |
| [AGENT_OUTCOME_EVALUATION.md](AGENT_OUTCOME_EVALUATION.md) | Agent outcome contracts: what is measured and what is not |
| [../VERSIONING.md](../VERSIONING.md) | What a version number promises; supported versions |

## For maintainers

Internal: how the project is planned, measured and changed. Not needed to
use the product.

| document | for |
|---|---|
| [../ROADMAP.md](../ROADMAP.md) | Milestones, gates and open decisions |
| [MASTERPLAN_TRACKER.md](MASTERPLAN_TRACKER.md) | Every masterplan item and its status |
| [adr/0001-version-semantics.md](adr/0001-version-semantics.md) | What version numbers mean and what is released |
| [WORKPLAN.md](WORKPLAN.md) | Work in progress, with every result and failure |
| [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) | What is implemented, task by task |
| [RESEARCH_ROADMAP.md](RESEARCH_ROADMAP.md) | The research agenda |
| [AUTHORIZATION_PROOF_RECEIPTS.md](AUTHORIZATION_PROOF_RECEIPTS.md) | Receipts that bind authorization decisions to evidence |
| [COMPONENT_REMOVAL_ABLATIONS.md](COMPONENT_REMOVAL_ABLATIONS.md) | Component removal experiments and their limits |
| [DECISION_FEATURE_PROVENANCE.md](DECISION_FEATURE_PROVENANCE.md) | Provenance fields available to decision models |
| [EVIDENCE_REQUIREMENT_GRAPHS.md](EVIDENCE_REQUIREMENT_GRAPHS.md) | Typed evidence requirements for governed actions |
| [LOCAL_PROTOCOL_EQUIVALENCE.md](LOCAL_PROTOCOL_EQUIVALENCE.md) | Matched MCP, UTCP and Code Mode workflows |
| [READ_ONLY_ADVISORIES.md](READ_ONLY_ADVISORIES.md) | Non-authoritative risk advisories and escalation |
| [REPRODUCIBLE_CORE_BUILD.md](REPRODUCIBLE_CORE_BUILD.md) | Reproducing the local core package artifacts |
| [SYSTEM1_ROUTING.md](SYSTEM1_ROUTING.md) | Calibrated fast-path decision routing |
| [UTCP_MANUAL_POLICY.md](UTCP_MANUAL_POLICY.md) | UTCP discovery under the existing authorization policy |
| [AI_SAFETY_CYBER_RESEARCH_IMPLEMENTATION_PLAN.md](AI_SAFETY_CYBER_RESEARCH_IMPLEMENTATION_PLAN.md) | The safety and security implementation plan |
| [../research/SCORECARD.md](../research/SCORECARD.md) | Every research claim and its outcome |
| [../RESEARCH.md](../RESEARCH.md), [../EVALUATION.md](../EVALUATION.md) | Research design and evaluation method |
| [BRANCHES.md](BRANCHES.md) | Branches and how they are protected |
| [../CONTRIBUTING.md](../CONTRIBUTING.md), [../AGENTS.md](../AGENTS.md) | How to change this repository |

## Memory Fabric 2 roadmap

- [Product and research masterplan](MEMORY_FABRIC_2_PRODUCT_RESEARCH_MASTERPLAN.md)
- [When ordinary vector retrieval is enough](product/WHEN_TO_USE_MEMORY_FABRIC.md)
- [Capability maturity matrix and claim gate](product/CAPABILITY_MATURITY.md)
- [Three product jobs to be done](product/JOBS_TO_BE_DONE.md)
- [Implementation status and compiler ADR](MF2_IMPLEMENTATION_STATUS.md)

## Current checklist work

- [Zero-budget validation and handoff](NO_BUDGET_VALIDATION.md)
- [Product readiness assessment](PRODUCT_READINESS.md)
- [0.14 SDK contracts](SDK_CONTRACTS_0.14.md)
- [Failure policies and external effects](FAILURE_POLICIES.md)
- [Memory Fabric migration plan](MEMORY_FABRIC_MIGRATION_PLAN.md)
- [Memory Fabric migration guide](MIGRATING_TO_MEMORY_FABRIC.md)
- [Memory Fabric migration report](MEMORY_FABRIC_MIGRATION_REPORT.md)
- [Memory Fabric release checklist](MEMORY_FABRIC_RELEASE_CHECKLIST.md)
- [Package publishing](PYPI_PUBLISHING.md)
- [Local three-agent and conformance audit](LOCAL_AGENT_AUDIT.md)
- [Experimental evidence completeness](EVIDENCE_COMPLETENESS.md)
- [Experimental historical reads](HISTORICAL_READS.md)
- [Operator import preview and atomic batches](IMPORT_PREVIEW.md)
- [Optional lossless phrase compaction](LOSSLESS_COMPACTION.md)
- [Checklist execution status](NEXT_CHECKLIST_STATUS.md)
- [Historical read security design](adr/0002-historical-belief-reads.md)
- [Procedural asset schema draft](adr/0003-procedural-asset-draft.md)
- [Product decision packet](product/decisions/2026-10-28-packaging-options.md)

## Engineering and research evidence

| document | for |
|---|---|
| [Action race serialization](ACTION_RACE_SERIALIZATION.md) | Concurrent action authorization ordering |
| [Benchmark manifest environment](BENCHMARK_MANIFEST_ENVIRONMENT.md) | Runtime, host and input evidence for benchmark runs |
| [Bitemporal history](BITEMPORAL_HISTORY.md) | Historical validity and belief-time reads |
| [Crash boundary matrix](CRASH_BOUNDARY_MATRIX.md) | Persistence behavior across process crashes |
| [E4 soak](E4_SOAK.md) | Local soak and recovery evidence |
| [Error contract matrix](ERROR_CONTRACT_MATRIX.md) | Error semantics across public adapters |
| [Event schema compatibility](EVENT_SCHEMA_COMPATIBILITY.md) | Event format upgrade rules |
| [Evidence chain selection](EVIDENCE_CHAIN_SELECTION.md) | Evidence chain ranking and constraints |
| [Evidence package budgets](EVIDENCE_PACKAGE_BUDGETS.md) | Bounded evidence packaging |
| [Evidence status API](EVIDENCE_STATUS_API.md) | Evidence sufficiency response contract |
| [Experimental defaults](EXPERIMENTAL_DEFAULTS.md) | Defaults and opt-in feature inventory |
| [Freshness leases](FRESHNESS_LEASES.md) | Federation evidence freshness |
| [Historical compatibility fixtures](HISTORICAL_COMPATIBILITY_FIXTURES.md) | Store compatibility test fixtures |
| [Historical surface security](HISTORICAL_SURFACE_SECURITY.md) | Access controls for historical reads |
| [Local check report](LOCAL_CHECK_REPORT.md) | Test outcomes and optional capability inventory |
| [Local footprint qualification](LOCAL_FOOTPRINT.md) | Installed size, CLI startup, SQLite growth and idle CPU on one host |
| [Support bundle](SUPPORT_BUNDLE.md) | Metadata-only diagnostics export and privacy boundary |
| [Upgrade preview](UPGRADE_PREVIEW.md) | Read-only schema compatibility diagnosis before opening a store writable |
| [Runbook drills](RUNBOOK_DRILLS.md) | Local outage, key loss, corruption and mass-retraction drills |
| [Offline qualification checklist](MEMORY_FABRIC_OFFLINE_10_OF_10_MASTER_CHECKLIST.md) | 260-item offline qualification scope |
| [Modifier evidence packages](MODIFIER_EVIDENCE_PACKAGES.md) | Evidence attached to memory modifications |
| [Next master checklist execution](NEXT_MASTER_CHECKLIST_EXECUTION.md) | Prior checklist evidence and remaining gates |
| [OAuth](OAUTH.md) | OAuth resource-server validation |
| [Action grant binding](ACTION_GRANT_BINDING.md) | Binding one-use grants to actions |
| [Action idempotency](ACTION_IDEMPOTENCY.md) | Retry and replay semantics |
| [Action reconciliation](ACTION_RECONCILIATION.md) | Recovering uncertain external effects |
| [Agent adapter](AGENT_ADAPTER.md) | Agent integration adapter contracts |
| [Agent scale benchmark](AGENT_SCALE_BENCHMARK.md) | Multi-agent scale benchmark method |
| [Correction timing benchmark](CORRECTION_TIMING_BENCHMARK.md) | Measuring correction propagation |
| [Evidence operation risk](EVIDENCE_OPERATION_RISK.md) | Operational risks in evidence handling |
| [Failure taxonomy](FAILURE_TAXONOMY.md) | Benchmark failure categories |
| [False withholding ablation](FALSE_WITHHOLDING_ABLATION.md) | Diagnosing valid evidence withheld by policy |
| [Matched agent arms](MATCHED_AGENT_ARMS.md) | Matched benchmark arms and controls |
| [Minority source benchmark](MINORITY_SOURCE_BENCHMARK.md) | Minority-source evidence benchmark |
| [Offline research benchmark](OFFLINE_RESEARCH_BENCHMARK.md) | Replaying offline benchmark suites |
| [Withheld cases](PR30_WITHHELD_CASES.md) | Reproduced withheld-evidence cases |
| [Retention and audit preservation](RETENTION_AND_AUDIT_PRESERVATION.md) | Retention and audit guarantees |
| [Safety completion tradeoff](SAFETY_COMPLETION_TRADEOFF.md) | Safety and task completion measures |
| [Withholding promotion gate](WITHHOLDING_PROMOTION_GATE.md) | Promotion criteria for withholding changes |
| [Package parity](PACKAGE_PARITY.md) | Installed wheel and source distribution parity |
| [Parameter equivalences](PARAMETER_EQUIVALENCES.md) | Equivalent parameterized query forms |
| [Portable paths](PORTABLE_PATHS.md) | Path, text encoding and case-collision behavior |
| [Typed SDK workflow](SDK_WORKFLOW.md) | Add, recall, correction, decision proposals and fenced execution |
| [Query routing](QUERY_ROUTING.md) | Deterministic retrieval routing behavior |
| [Read surface semantics](READ_SURFACE_SEMANTICS.md) | Shared read response reason codes |
| [Result provenance](RESULT_PROVENANCE.md) | Exact commit and dirty-tree result binding |
| [Retrieval baseline qualification](RETRIEVAL_BASELINE_QUALIFICATION.md) | Retrieval acceptance gates and caveats |
| [Retrieval index invalidation](RETRIEVAL_INDEX_INVALIDATION.md) | Index update and invalidation rules |
| [Seed manifests](SEED_MANIFESTS.md) | On-disk seed output verification |
| [Stage tracing](STAGE_TRACING.md) | Retrieval stage measurements |
| [State transitions](STATE_TRANSITIONS.md) | Lifecycle transition contract |
| [Tombstone exchange](TOMBSTONE_EXCHANGE.md) | Retraction propagation protocol |

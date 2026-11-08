# Candidate contributions and prior mechanisms

This is a research plan, not a novelty or efficacy claim. Each sentence below
states a falsifiable hypothesis relative to mechanisms already in this
repository. A result that fails its preregistered comparison remains a negative
result; it does not become a contribution by changing the wording afterward.

## Falsifiable main-contribution sentences

| Direction | Main contribution hypothesis | Primary comparison and falsifier |
|---|---|---|
| Correction-aware decision continuity (**NOT_PROVEN**) | At equal evidence and action budgets, an incremental decision-to-premise dependency index will identify every affected decision after correction while causing fewer unrelated re-evaluations than the existing lineage scan and blanket invalidation. | [Registered N1-10 protocol](prereg/n1-10-decision-repair-novelty.md): compare matched governance-only, blanket invalidation, and decision-repair arms on held-out cases; falsified by any missed affected decision, unauthorized effect, or failure to meet the safe-completion and false-abstention gates. |
| Proof-carrying evidence sufficiency | At a fixed retrieval and context budget, action-specific requirement certificates will reduce false authorization without increasing valid-evidence withholding beyond the preregistered tolerance of the current `answerability` baseline. | Compare current answerability, policy-only blocking and exhaustive small-graph oracle; falsified by unsafe authorization, excess false withholding or an oracle ceiling with no headroom. |
| Provenance-preserving consolidation | At equal stored-byte and retrieval budgets, consolidated summaries retaining source dependency links will preserve corrected-task decisions better than extractive summaries and ordinary compaction after source retraction. | Compare exact history, extractive summary and ordinary compaction; falsified by a stale summary-supported action or no matched-budget benefit. |

These sentences are hypotheses only. They do not say the mechanism is novel in
the global literature or that an experiment has passed.

## Contribution-by-component and prior-work table

| Candidate mechanism | Existing repository mechanism that predates the study | Contribution that would need to be new | Credited baseline and current evidence |
|---|---|---|---|
| Incremental decision dependency index | Memory lineage, transitive correction/retraction, action certificates and revalidation already exist. | A separately typed decision graph and incremental affected-decision query with equivalence to a full-scan oracle and measured update-cost bound. | `src/memory_fabric/lineage.py`, `src/memory_fabric/certificates.py`, `tests/test_transitive_retraction.py`; current stale-action gate remains the baseline. |
| Action-specific evidence requirement graph | Action-time authorization, evidence sufficiency and abstention already exist. | A declarative AND/OR/independence/temporal requirement grammar with minimal missing-evidence explanations and proof-carrying receipts. | `src/memory_fabric/answerability.py`, `src/memory_fabric/actions.py`, `tests/test_certificates.py`; compare against current answerability and policy-only guards. |
| Provenance-preserving consolidation | Derivation lineage, corrections, retraction propagation and experimental Context Map summaries already exist. | A summary representation whose supported claims retain dependency proofs and whose unsupported claims invalidate under source correction, with matched-byte comparisons. | `src/memory_fabric/lineage.py`, `src/memory_fabric/context_map.py`, `tests/test_context_map.py`; exact history and ordinary compaction are required baselines. |

## Promotion boundary

Before making a scientific contribution claim, preregister the mechanism,
primary outcomes, baseline versions, data generator, seeds, budget, falsifier
and stopping rule. Use held-out task families and report all safety, utility,
latency, storage and cost outcomes. A positive synthetic result supports only
the registered synthetic workload until independently reproduced.

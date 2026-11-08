# Research failures, killed hypotheses and inconclusive outcomes

This is a taxonomy of the registered historical comparison tracks named here,
not a claim that every experiment in the repository has been independently
re-audited. Keep the original result and preregistration as the authority; this
index preserves failure mechanism and what evidence would change the next test.

| Track and verdict | Failure class | What failed or did not generalize | Causal explanation supported by the recorded result | Next test boundary |
|---|---|---|---|---|
| H2 — KILLED | Metric-to-decision mismatch; weak headroom | Credit-driven retention beat frequency and recency but did not beat a smoothed-success baseline: −0.012 [−0.025, +0.002]. The naive baseline captured 93.2% of oracle gain. | Whole-population rank correlation was not the decision-relevant bottom-of-budget ranking; directly observable harm made the simple success baseline strong. The store also did not grow, so credit-driven writing was untested. | Re-register only with a binding budget/growing store and a primary metric shown not to be saturated by simple baselines; do not reinterpret the original verdict. |
| PA — KILLED | Governance overhead and harmful attribution | The governed arm scored 0.283 against the strongest ungoverned arm at 0.583; naive blame was actively harmful. | The governance path spent more tokens and withdrew useful memories on surface association; fixed local-model workload and task set limit generalization. | A new preregistration must isolate a mechanism, match budget and include ordinary retrieval, causal attribution, and a fair oracle. |
| PA′1 — KILLED; PA′2 — SUPPORTED | Attribution tradeoff; success/efficiency regression | Leave-one-out recovered much of blame's damage but remained 0.125 below shared memory, used 2.55 calls per episode and 3.4× tokens. | Leave-one-out can remove irrelevant-but-useful memories because removing distraction can help one episode; this does not prove the source fact is false. | Test an independently preregistered applicability/contradiction signal; include cost and valid-withdrawal rates. Keep PA′1 killed and PA′2 supported as separate verdicts. |
| PB1 — KILLED | No selective-sharing gain; fairness regression | `share_overlap` vs `share_all` was +0.008 [−0.042, +0.058] and worst-agent success fell from 70.0% to 68.3%. | A memory wrong at one site could still be useful at another site for the same recipient; static recipient-level filtering loses coverage. The oracle ceiling was also invalid because several arms beat it. | Move filtering to action-time context, repair the oracle, and preserve worst-agent/fairness outcomes. The ceiling failure invalidates headroom fractions, not PB1's arm-to-arm kill conditions. |
| PB3 — INCONCLUSIVE | Missing implementation | Reputation weighting was not implemented, although the run had imports that could have supported it. | No treatment arm existed; this is missing work, not evidence for or against reputation. | Implement only under a new registration with explicit reputation inputs, leakage controls and matched comparisons. |

## Claims that remain NOT_TESTED or EXTERNAL

| Claim | Status | Why it cannot be measured by these local results |
|---|---|---|
| Performance and robustness across multiple real model families | NOT_TESTED | Historical local Qwen runs use one model family; deterministic TeamWorld has no language model. |
| Human usefulness, pilot success, buyer demand or willingness to pay | NOT_TESTED | No representative participant or customer pilot data is present. |
| Physical multi-host convergence under network partition and clock skew | NOT_TESTED | Single-host/in-process simulations are not independent hosts or real network partitions. |
| Independent security assurance | EXTERNAL | Repository tests are not a commissioned human audit or independent red team. |
| Global scientific novelty or patentability | EXTERNAL | Repository comparison and source reading do not replace source-aware external literature and patent review. |

Do not turn these labels into an inferred negative result: no local measurement
means the claim remains untested, not that it is false or supported.

## Interpretation rules

- A killed hypothesis is not repaired by a later, differently scoped positive
  result; retain both with their distinct populations, baselines and metrics.
- An invalid oracle invalidates ceiling/headroom claims that depend on it. It
  does not erase independent preregistered arm-to-arm criteria.
- Inconclusive due to an unbuilt arm is not a null effect.
- Local-model or synthetic outcomes are not independent replications or
  customer evidence.

## Source records

- [H2 result](results/h2-credit-driven-retention.md) and [H2 preregistration](prereg/h2-credit-driven-retention.md)
- [PA result](results/phase-a-real-agent-benchmark.md) and [PA preregistration](prereg/phase-a-real-agent-benchmark.md)
- [PA′ result](results/phase-a-prime-attribution.md) and [PA′ preregistration](prereg/phase-a-prime-attribution.md)
- [Phase B result](results/phase-b-federated-agents.md) and [PB preregistration](prereg/phase-b-federated-agents.md)

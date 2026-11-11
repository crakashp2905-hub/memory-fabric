# R5-03 one-component removal study

`research/results/r5-03-component-removal.json` compares each named mechanism
with a matched component-absent arm. The outcomes are marginal differences for
these fixtures, not gains attributable to the whole integrated system.

| Component | Enabled | Removed | Paired marginal effect |
|---|---|---|---|
| Summary dependency validation | Refused a stale summarized fact after its source changed | A text-only reader exposed the old fact | The check blocked the stale fact in this one correction case |
| Risk/evidence-aware routing | 0 unsafe System 1 routes and 0 unnecessary System 2 routes across 2,000 tasks | Fixed System 1 produced 495 unsafe routes; fixed System 2 produced 1,505 unnecessary escalations | Routing utility was +1.361 versus fixed System 1 and +0.602 versus fixed System 2 under declared synthetic costs |
| Provenance-preserving compaction | 100% task success, 0 stale actions, 5,242 mean UTF-8 context bytes | Full history: 100% success, 0 stale actions, 8,647 mean bytes | 3,405 bytes saved (39.4%) with no success or stale-action change across five paired seeds |

The dependency ablation deliberately ignores the dependency result and summary
lifecycle flag to isolate the fact-to-version check. The router's hazard labels
are generated from the same features it consumes. The compression results reuse
the deterministic N4-07 temporal fixture. These are exploratory synthetic
contract measurements: no confidence intervals, human evaluation, live agents,
external baselines, token counts, or deployment-cost estimates are included.

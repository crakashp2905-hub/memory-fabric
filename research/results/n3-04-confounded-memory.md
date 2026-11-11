# N3-04 — Confounding by task difficulty

In 4,000 seeded episodes, the memory's oracle average treatment effect is
`+0.15`. The retrieval policy exposes it in 90.6% of easy tasks and 9.8% of
hard tasks, so the exposed group has a much higher success rate even before
credit is assigned.

| Measure | Result |
|---|---:|
| Naive exposed-minus-withheld association | 0.5538 |
| Naive overstatement vs oracle effect | 0.4038 |
| IPS estimate | 0.1606 |
| IPS absolute error | 0.0106 |
| IPS 95% interval | [0.1348, 0.1864] |

The propensity-corrected estimate preserves the known positive effect and
exposes the extra apparent value caused by task selection. This is simulated
evidence with known, correctly logged assignment probabilities; it does not
address hidden confounding or adaptive real-world retrieval.

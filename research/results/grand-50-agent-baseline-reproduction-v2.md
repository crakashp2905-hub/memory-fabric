# Grand 50-agent baseline reproduction v2

The historical PR #30 baseline was rerun in a clean detached worktree at
commit `d4fd174ac9056865c8b73abd857fa681daa6a0d7` on 2026-11-01. The five
registered unseen seeds reproduced the published aggregate exactly.

| Metric | Original | Reproduction | 95% bootstrap CI over seeds | Denominator |
|---|---:|---:|---:|---:|
| Task success | 58.4% | 58.4% | 55.0–61.6% | 500 answerable tasks |
| Valid evidence withheld | 16.8% | 16.8% | 13.0–19.8% | 500 answerable tasks |
| Stale action | 0.0% | 0.0% | 0.0–0.0% | 500 task decisions |

`valid evidence withheld` means the world oracle has a current fact, the
backend still holds a statement containing that exact current value and the
retrieved context does not contain it. It is evaluated after retrieval and any
permitted rediscovery. It is not a claim that inaccessible evidence was
withheld. `stale action` means the deterministic agent answered with the value
recorded as superseded by a correction.

The zero-event bootstrap interval is descriptive rather than an upper safety
bound. Release evidence must additionally report a binomial zero-event bound.
This run uses a deterministic agent and simulated world; it is not a real-model
or physical multi-host result.

Machine-readable evidence: [grand-50-agent-baseline-reproduction-v2.json](grand-50-agent-baseline-reproduction-v2.json).

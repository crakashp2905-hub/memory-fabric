# LongMemEval `s`-100 reproduction v2

Run on exact commit `beadf2c2126326aecf91beae07fcdd6dfaf69a87` using
the upstream `longmemeval_s_cleaned.json` bytes with SHA-256
`d6f21ea9d60a0d56f34a05b609c79c88a451d2ae03597821ea3d5a9678c3a442`.
The clean run used 100 deterministic stratified instances, `k=10`, and the
`as_of` temporal mode.

| Arm | Turn recall | Session recall | Any gold turn | Mean retrieval latency | Wall time |
|---|---:|---:|---:|---:|---:|
| Lexical | **73.85%** | 93% | 82% | 25.80 ms | 395.5 s |
| Hybrid | 69.17% | 92% | 79% | 29.05 ms | 454.3 s |

The historical values reproduced exactly. The registered claim that hybrid
would exceed lexical fails. These are retrieval metrics from an external
corpus, not end-to-end answer quality. The corpus README does not state a
dataset licence, so this is internal qualification evidence rather than a
redistributable artifact.

Machine-readable result: [longmemeval-s100-reproduction-v2.json](longmemeval-s100-reproduction-v2.json).

# N1-09 Decision Continuity Benchmark

**Source commit:** `6ee07f1add39dd07b465d117735a2b319082ea0a`  
**Machine-readable result:** [`n1-09-decision-continuity.json`](n1-09-decision-continuity.json)  
**Result SHA-256:** `42af4b9fbac87e9f6e037851a1cdb60d646b5f61b72b6cce0caf6225a768cd0`  
**Environment:** Windows 11, Python 3.13.5  
**Workload:** five deterministic seeds, 2,000 decisions per seed, 10% target correction rate.

## Results

| Strategy | Re-evaluations / 2,000 | Unnecessary re-evaluations | Stale decisions | Correctly routed | Median update cost |
|---|---:|---:|---:|---:|---:|
| Plain memory versioning | 0 | 0 | 196 | 90.2% | 0.2 µs |
| Blanket invalidation | 2,000 | 1,804 | 0 | 9.8% | 16.2 µs |
| Exact dependency index | 196 | 0 | 0 | 100% | 1.586 ms |

The exact index matched the deterministic oracle for all five seeds and scanned
exactly one newly appended correction event per run. Its median warm-index
build time was 291.8 ms over 4,000 decision and reliance events. It routed about
90% fewer decisions to re-evaluation than blanket invalidation and produced no
stale or unnecessarily blocked decisions in this fixture.

Update timings measure the strategy's routing/update operation only. In
particular, they exclude model inference and use different computational
operations for the three strategies; they are descriptive local measurements,
not an equal-work latency comparison. “Correctly routed” means an affected
decision is flagged for review while an unaffected decision remains usable.

## Reproduction

```powershell
python tools/n1_09_decision_continuity.py --write research/results/n1-09-decision-continuity.json
python -m pytest tests/test_n1_09_decision_continuity.py -q
```

The JSON records each seed, dataset digest, source commit, dirty-tree marker,
index build time, hot correction cost, routing counts, platform and limitations.
The benchmark uses a deterministic synthetic oracle, performs no model-assisted
re-evaluation, and executes no external action. It is not evidence of real-agent
task success or population performance.

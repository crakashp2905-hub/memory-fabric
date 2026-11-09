# Offline synthetic research benchmark

The suite needs only Python and the repository's standard-library benchmark code. From a fresh checkout, run:

```powershell
python -m benchmarks.offline_research
```

This writes `research/results/r1-offline-synthetic.json`. It deterministically regenerates the train/dev/test worlds, checks schema and split leakage, records each preregistered case and every control decision, then reports task-level denominators, Wilson intervals, zero-event upper bounds, and declared local model/token cost. The JSON contains a registered case count and per-world hashes; a count or hash change requires a new preregistered benchmark version. Compare two outputs by comparing their sorted JSON after parsing; identical code and inputs produce identical scenario hashes and decisions.

The run is `synthetic_scripted`, not a real-model evaluation. It makes no latency claim: wall-clock timing varies by host and is intentionally not used as a decision metric in this deterministic replay. Model/API cost is zero because no model or external service is called. To qualify runtime or model costs, add a separately registered arm and report its population and cost basis.

Run focused checks with:

```powershell
python -m pytest tests/test_offline_research.py -q
```

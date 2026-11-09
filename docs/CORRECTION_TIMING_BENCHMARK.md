# Correction timing benchmark

Run with:

```powershell
python -m benchmarks.correction_timing
```

The report at `research/results/r3-04-correction-timing.json` runs 50 scripted agents over three seeds and three correction stages. It includes corrected cases and unchanged supported controls. `cached_local` never refreshes its initial evidence; `pooled_recheck` refreshes before planning; Memory Fabric rechecks at the action gate. The report measures the exact event order and stale-action counts. Its elapsed times are host-dependent and are not latency claims.

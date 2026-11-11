# Scripted agent scale benchmark

From a clean checkout run:

```powershell
python -m benchmarks.agent_scale
```

The command runs the frozen 5/10/25/50/100-agent matrix over seeds 701, 709, and 719 and writes `research/results/r3-01-agent-scale.json`. Each seed uses the same eight tasks at every scale (two each for supported, corrected, contested, and missing evidence). The report includes the task IDs, per-family denominators, authorization outcomes, host environment, input hashes, and timing. This evaluates scripted agents sharing one local store; it is not a real-model performance result. Zero unsafe actions in this finite synthetic sample is not a universal guarantee.

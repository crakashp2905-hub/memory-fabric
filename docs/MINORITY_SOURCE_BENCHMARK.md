# Minority source benchmark

Run with:

```powershell
python -m benchmarks.minority_source
```

The report at `research/results/r3-05-minority-source.json` compares a one-source majority of 49 repeated claims against one independent minority source across three seeds. It reports the minority agent, majority mean, and population mean separately for majority-vote, minority-source, Memory Fabric, and oracle arms. The current synthetic case intentionally creates contested evidence: the report therefore exposes whether the gate preserves an independently supported minority claim or withholds it. It is not a claim about human or model-agent consensus behavior.

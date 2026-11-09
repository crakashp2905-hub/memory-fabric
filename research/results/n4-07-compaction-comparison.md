# N4-07 compaction comparison

**Evidence level:** `SIMULATED` — deterministic synthetic agent contract.
**Seeds:** `11, 23, 37, 41, 59`; **tasks:** 40 per arm.

| Arm | Success | False stale actions | Mean bytes | Compression factor | Identity fidelity | Factual fidelity |
|---|---:|---:|---:|---:|---:|---:|
| `no_compaction` | 1.000 | 0 | 8647.0 | 1.000 | 1.000 | 1.000 |
| `naive_recency` | 0.300 | 0 | 3264.2 | 2.649 | 0.375 | 0.375 |
| `extractive_summary` | 0.500 | 20 | 701.0 | 12.335 | 0.000 | 1.000 |
| `provenance_preserving_summary` | 1.000 | 0 | 5242.0 | 1.650 | 1.000 | 1.000 |

This is a descriptive fixture comparison, not evidence of real-agent efficacy.
Byte counts are UTF-8 payload sizes and are not token or model-cost estimates.
The full-history arm is a fixture ceiling; any method above it invalidates the run.
Exact inputs, per-seed values, test status, and source provenance are in the JSON.

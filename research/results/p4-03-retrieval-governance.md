# P4-03 · ordinary retrieval and governed correction continuity

Run: `python -m experiments.p4_03_retrieval_governance --out research/results/p4-03-retrieval-governance.json`.
The JSON records the source commit, dirty-tree flag, Python/OS/SQLite versions,
input digests, all 20 case outcomes and the metric denominators.

The fixed synthetic set contains four cases in each of five setting families.
Both arms receive an initial value and a reviewed correction. The ordinary
SQLite/JSON arm reads the newest version for the current task while retaining a
previously cached action. It has no authorization API, so that stale outcome is
reported as **WOULD EXECUTE**, not as an observed side effect. The governed arm
retrieves the corrected value, attempts the cached action through the
`ActionGate`, then attempts the corrected action.

| Arm | Corrected tasks completed | Stale action outcomes |
|---|---:|---:|
| Ordinary latest-version retrieval | 20 / 20 | 20 / 20 WOULD EXECUTE from cache |
| Memory Fabric governed retrieval | 20 / 20 | 0 / 20 executed |

The regression test runs the complete matrix twice and compares the structured
results. This result supports the narrow claim that, in these authored
correction scenarios, action-time governance prevents stale cached actions
without reducing corrected-task completion. It is not a real-agent evaluation,
held-out benchmark, production estimate, or latency/cost measurement. It does
not establish general retrieval superiority. The ordinary adapter's stale
outcome is counterfactual because it has no gate and the benchmark calls no
external tool.

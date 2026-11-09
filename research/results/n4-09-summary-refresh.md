# N4-09 summary refresh profile

**Evidence level:** `CONTRACT`; local deterministic operation-count study.

| Arm | Mean writes after corrections | Mean total writes | Mean source inputs reprocessed |
|---|---:|---:|---:|
| `affected_refresh` | 3.0 | 9.0 | 24.0 |
| `complete_rebuild` | 18.0 | 24.0 | 144.0 |

One of six sessions receives each of three corrections. The affected-refresh
arm rebuilds one session summary per correction and leaves unaffected summaries
unchanged. Same-seed final content hashes are identical across repeated runs.
This is operation-count evidence, not a latency or production-scale claim.

# Benchmark manifest environment

`mf-run-manifest/1` records capture Python, OS, SQLite, logical CPU count,
active thread count, and active child-process count from the run host. The
environment block contains no wall-clock fields. Validation rejects missing or
empty environment values, and canonical manifest digests exclude timestamps.

All five active manifests under `research/results/bench_runs/` were regenerated
from a clean checkout at commit `9260e482e05831db72afdada5820220448c15003`.
Each carries the six required host fields, exact source SHA, `dirty: false`, and
SHA-256 input digests. `tests.test_benchmarks.Manifests.test_recorded_runs_are_valid`
checks these fields and runs the strict validator over every active manifest.

The five manifests that predated environment capture are preserved byte-for-byte
under `research/results/bench_runs/legacy/`. Their hashes and unqualified status
are listed in `legacy/index.json`; historical host details and missing full
source SHAs are not reconstructed. The active manifest reader is non-recursive,
so archived records cannot enter the scoreboard.

The manifest digest hashes canonical JSON and excludes `timestamp`,
`created_at`, `updated_at`, and `built_at` keys at every object level. Active
manifests declare SHA-256 digests for their dataset generators and inputs. The
scoreboard verifies these digests before including a run; a mismatch aborts
aggregation.

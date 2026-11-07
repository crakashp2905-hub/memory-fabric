# Benchmark manifest environment

New `mf-run-manifest/1` records capture Python, OS, SQLite, logical CPU count,
active thread count, and active child-process count when the manifest object is
created. The environment block contains no wall-clock fields.

`benchmarks.manifest.validate` rejects a missing or empty environment field.
`benchmarks.manifest.digest` hashes canonical JSON and excludes timestamp keys
(`timestamp`, `created_at`, `updated_at`, and `built_at`) at every object level.

The five checked-in `research/results/bench_runs` records predate this
requirement and do not contain environment measurements. They remain readable
for provenance, but the strict parser reports them as unqualified. Their
historical host details are not reconstructed or guessed.

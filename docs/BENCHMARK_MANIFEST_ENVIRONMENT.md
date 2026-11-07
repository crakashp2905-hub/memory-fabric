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

Executed benchmark manifests also record SHA-256 digests for declared dataset
inputs and their generator script. The scoreboard verifies those digests before
including a run. Legacy manifests without input digests remain archived and are
excluded; a digest mismatch aborts scoreboard generation.

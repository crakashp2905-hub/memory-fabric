# Seeded experiment output manifests

Seeded experiments can register their expected outputs in a
`memory-fabric-seed-manifest/1` JSON file:

```json
{
  "schema": "memory-fabric-seed-manifest/1",
  "declared_seeds": [11, 12],
  "outputs": [
    {"seed": 11, "path": "research/results/run-seed-11.json"},
    {"seed": 12, "path": "research/results/run-seed-12.json"}
  ]
}
```

Each result file must be a JSON object with the matching integer `seed` field.
Run `verify_seed_manifest` from `tools/offline_qualification.py` before
accepting scores. Missing files/seeds, duplicate outputs, extra seeds, invalid
JSON, and paths that escape the repository are blockers.

# Metadata-only support bundle

Generate an aggregate diagnostics file with:

```powershell
memory-fabric --db project.db support-bundle --out support-bundle.json
```

The command writes schema/product versions, runtime versions, aggregate memory
and event counts, lifecycle/type counts and SQLite page metrics. It excludes
memory text, memory IDs, tenant names, encryption keys and event payloads.
Counts can still reveal rough store size; review the output before sharing it.
The command does not upload or transmit the bundle.

The contract is covered by a canary test that puts unique protected text and
identifiers into a store and checks the complete serialized bundle for their
absence: `tests/test_support_bundle.py`.

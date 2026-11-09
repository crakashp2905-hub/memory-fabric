# Portable tombstone exchange

`memory_fabric.tombstones` provides an offline, content-free transfer format
for exact-version federation retractions.

```python
from memory_fabric.tombstones import export_bundle, import_bundle

export_bundle(origin, "tombstones.json", since_sequence=0)
report = import_bundle(
    recipient,
    "tombstones.json",
    trusted_origins=[origin.store_id],
)
```

Import has no trust-by-default mode. The operator must list the opaque origin
store ID explicitly. The file format does not itself authenticate that ID;
offline transport, a detached signature, or another authenticated channel must
establish provenance before opt-in.

Each tombstone names an origin store, memory ID, and exact version. Importing a
tombstone after its snapshot quarantines the held imported version. Importing
it before a snapshot durably records the unknown-memory outcome in the inbox;
`accept_offer` then refuses that exact origin version if the snapshot arrives
later. Reimports are idempotent. A retraction of version 1 does not block a
distinct version 2.

The JSON envelope is `memory-fabric-tombstones/1` and includes only protocol
retraction metadata—never memory content. `through_sequence` supports
incremental exchange; consumers should retain their last accepted watermark.

Executable orderings, trust refusal, idempotency, and content exclusion are in
`tests/test_tombstone_exchange.py`.


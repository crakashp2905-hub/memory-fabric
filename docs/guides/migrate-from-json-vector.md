# Move from JSON or vector recall in 15 minutes

This is a small, reversible first migration. It copies text memories and their
source IDs/authors into a new Memory Fabric store as **private candidates**.
It does not modify the source export or import an embedding index. Keep the
old system available until the migrated records and owner mapping are checked.

The bundled fixture at
[`examples/fixtures/basic-memory-export.jsonl`](../../examples/fixtures/basic-memory-export.jsonl)
contains Mem0-style, LangChain `Document`-style and plain JSON records.
`tests/test_migration_guide.py` runs the same migration and verifies source
preservation, imported ownership and review behavior.

## Minutes 0–3: export and protect the source

Export one record per JSON line. Include a stable source ID, the memory text,
and the original user/agent that wrote it. For example:

```json
{"id":"mem-001","content":"Pump P1 purge time is 30 seconds.","agent_id":"alice"}
```

Keep the original database and vector index read-only. Make a separate export
copy and record its hash before importing:

```console
python -c "import hashlib,pathlib; p=pathlib.Path('export.jsonl'); print(hashlib.sha256(p.read_bytes()).hexdigest())"
```

Memory Fabric imports content and recognized identity/source fields. It does
not use old vectors as Memory Fabric embeddings; preserve those files with the
source system and rebuild an index using your chosen retrieval adapter if
needed.

## Minutes 3–6: create an isolated target

```console
memory-fabric init ./memory-fabric-migration --agent migration-bot --mode team
memory-fabric --db ./memory-fabric-migration/store.db doctor
```

The new store has its own event log, external key directory, and server-only
agent file. For a tenant-per-store deployment, create one target per tenant.
When several tenants share one store, import each tenant export separately
with its explicit `--tenant` ID; do not merge owners across tenants.

## Minutes 6–9: import without trusting the records

```console
memory-fabric --db ./memory-fabric-migration/store.db --json import export.jsonl --source legacy-json --agent migration-bot --tenant tn_default
```

The command reports imported, skipped, quarantined and duplicate records.
Unknown record shapes are skipped with line numbers. Imports are private
candidates, even if the source record says it was previously approved. An
imported author string records attribution; it does not create an authenticated
Memory Fabric identity or grant permissions. Review secrets or prompt
injection quarantines individually; do not use an override just to increase
the import count.

## Minutes 9–12: verify and review

Inspect the queue and check a sample against the original export:

```console
memory-fabric --db ./memory-fabric-migration/store.db --json review
memory-fabric --db ./memory-fabric-migration/store.db show <memory-id>
```

Compare `source_id`, `imported_from`, `created_by`, tenant, and content. Approve
only records with verified ownership and meaning:

```console
memory-fabric --db ./memory-fabric-migration/store.db review <memory-id> --approve --actor <reviewer>
```

Approval makes the memory team-visible. If it should remain limited to its
author, choose `--limit` instead. Review decisions are recorded in the target
store. The original export remains untouched and is the rollback source.

## Minutes 12–15: compare, then canary

Re-run the same sample queries against both systems. Compare returned text,
source IDs and owners; also check that unreviewed imports remain hidden and
that reviewed content is visible only at its approved scope. Recompute the
export hash and confirm it matches the original.

Start with a low-risk read-only canary. Keep the old store intact until the
owner mapping, review queue, correction path and application behavior are
accepted. There is no automatic live dual-write between the stores. Rollback
means sending reads back to the old system; do not delete it as part of this
guide. See [Migration](../MIGRATION.md#moving-in-from-another-memory-system)
for accepted record formats and [Quickstart](../QUICKSTART.md) for the
governed correction workflow.

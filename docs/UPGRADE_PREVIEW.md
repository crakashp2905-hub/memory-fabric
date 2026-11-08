# Read-only upgrade preview

Inspect a SQLite store before opening it through a writer with:

```powershell
memory-fabric --db project.db upgrade-preview
```

The command opens SQLite with `mode=ro`, reports event count, recorded schema
versions, `PRAGMA quick_check`, current reader compatibility and the database
SHA-256 before and after inspection. It exits 5 when the event schema is
malformed, newer or outside the current reader's major-version range. A clean
exit means only that these structural checks passed; it does not simulate a
future migration or prove application-level semantics. PostgreSQL is not
supported by this preview.

The operation performs no migration and fails the byte-identity check if the
database changes during inspection. See `tests/test_upgrade_preview.py` for
supported, malformed and newer-schema fixtures.

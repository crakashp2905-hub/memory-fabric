# Core lifecycle crash-boundary matrix

`tests/test_multiprocess_crash.py` uses child processes that terminate with
`os._exit(70)`: no Python cleanup, database close, or `finally` handler runs.
For every core lifecycle operation—append, correct, withdraw, erase, branch
commit, and governed merge—the same operation is killed at three boundaries:

| Boundary | Injection point | Required reopened state |
|---|---|---|
| Event inserted, chain not extended | `IntegrityChain.extend` is replaced in the child with a hard exit | No event, no projection change, original valid hash chain |
| Event and chain staged, transaction not committed | Operation runs inside an outer store transaction, then hard exit | No operation effect, original head and valid hash chain |
| Transaction committed | Operation returns, then immediate hard exit | Entire operation visible, advanced head and valid hash chain |

Every reopened database is replayed and its integrity chain verified. Branch
commit and merge cover multi-event operations, not only single-row lifecycle
changes. The surrounding suite also kills durable retraction/outbox commits,
forwarded retractions, lost acknowledgements, and repeated mixed boundaries.

The guarantee is database atomicity on the local SQLite implementation. It
does not claim filesystem durability beyond SQLite's configured guarantees or
equivalence on PostgreSQL; backend-specific crash qualification remains a
separate deployment gate.


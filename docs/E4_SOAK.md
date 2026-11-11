# E4-10 crash, restore, and resource soak

Run the deterministic local qualification with:

```powershell
python -m experiments.e4_soak --cycles 40
```

The harness requires `psutil` for child-process RSS sampling. Each cycle uses a
separate child process to append and commit one correction and then terminates
with `os._exit` before cleanup. Every ten cycles the parent verifies the
integrity chain, creates a replay-verified backup, restores into a new
directory, checks that the outbox still matches the recipient's reconciliation
cursor, replays missed corrections, and confirms idempotent delivery settles
the restored outbox.

The run fails if any of these bounds are crossed: 128 MiB per database file,
384 MiB of temporary soak data, 512 MiB peak child RSS, 256 MiB parent traced
Python allocations, ten pending rows at a checkpoint, or a last-to-first
quartile p99 restart-latency ratio above 3. The JSON result contains each
restart duration, checkpoint state, environment details, and the pass decision.

This is reproducible local SQLite evidence. It does not qualify a 24-hour
production soak, PostgreSQL, a physical host failure, or resource ceilings on
deployment hardware. Those remain separate gates.

# Local incident runbook drills

Run all local drills and write the machine-readable report:

```powershell
python tools/runbook_drill.py --drill all
```

Or run one with `--drill outage`, `key-loss`, `corrupt-db`, or
`mass-retraction`. The drills cover a temporarily unavailable federation
recipient, a missing external key store, a tampered event chain, and a
100-descendant correction/retraction cascade. They use local fixtures and
never contact a remote peer or external service.

The default report is `research/results/p3-10-runbook-drills.json`. The outage
and corruption drills simulate failure modes in-process; they are not physical
network or arbitrary storage-failure exercises. Tests verify every selector
and check the 100-descendant result.

If a store is irrecoverable, stop writes and preserve the original database and
key material for investigation. Restore only from a separately verified backup
and matching keys; if the required key is permanently lost, encrypted content
cannot be recovered. Do not claim successful recovery from metadata-only checks.

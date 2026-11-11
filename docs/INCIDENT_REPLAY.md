# Replay a redacted incident explanation

The Control Center and `incident --record` can produce a content-free action
trace. A support engineer can verify and render the explanation from the
redacted JSON file without access to the store:

```powershell
python tools/replay_redacted_incident.py support-incident.json
python tools/replay_redacted_incident.py support-incident.json --out explanation.json
```

Replay checks the canonical report SHA-256 before producing a stable summary
of the recorded decision, reason codes, evidence versions, necessary source
IDs, and later withdrawals. The same artifact produces byte-identical output.
The command does not re-run authorization or reconstruct from the original
event history; it replays the explanation already present in the export. The
digest detects accidental edits, not malicious replacement or the identity of
the sender. Memory text is absent, though pseudonymous identifiers remain.

Generate a local regression result with:

```powershell
python tools/incident_replay_smoke.py
```

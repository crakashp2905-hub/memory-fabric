# Runbooks

What to do, in order, for the situations an operator meets. Every command here
exists and is tested; where a step is still a Python call rather than a
command, it says so. Procedures already written elsewhere are linked, not
copied, so the two cannot drift:

| Situation | Where |
|---|---|
| Install and first run | [README](../README.md#quick-start), [DEPLOYMENT.md §2](../DEPLOYMENT.md#2-running-the-server) |
| Backup and restore | [DEPLOYMENT.md §1](../DEPLOYMENT.md#backup), [OPERATIONS.md §2](OPERATIONS.md#backup) |
| Upgrade and rollback | [OPERATIONS.md §4–5](OPERATIONS.md#4-upgrades) |
| Erasure or subject-access request | [OPERATIONS.md §3](OPERATIONS.md#answering-a-subject-access-or-erasure-request) |
| "The event chain does not verify" | [OPERATIONS.md §3](OPERATIONS.md#the-event-chain-does-not-verify) |
| "A store will not open: KeyUnavailable" | [OPERATIONS.md §3](OPERATIONS.md#a-store-will-not-open-keyunavailable) |
| "The database is locked" | [OPERATIONS.md §3](OPERATIONS.md#the-database-is-locked) |
| Prompt injection, unsafe non-action, cross-tenant leak, model hash mismatch | §9-§12 below |

The rest are below.

---

## 1. A credential has leaked

**Goal:** the leaked credential stops working before anything else is done.

1. Revoke it. Paste the token on stdin so it does not reach shell history:
   ```bash
   memory-fabric --db store.db agent-api-revoke --agents-file agents.txt --token -
   ```
   If you do not have the token itself, cut the agent off entirely:
   ```bash
   memory-fabric --db store.db agent-api-revoke --agents-file agents.txt --agent <agent-id>
   ```
   Revocations are rows in the store. A running `agent-api` on the same store
   refuses the credential **on its next request**; nothing needs restarting
   (`tests/test_cli_revoke.py`).
2. If the agent's *signing key* leaked, not only one credential, rotate it (§2).
   Revoking credentials does not stop the key minting new ones.
3. Find what it wrote. Every memory records the agent that created it:
   ```bash
   memory-fabric --db store.db list --agent <agent-id> --limit 0
   ```
   and the full event history of any one of them with
   `memory-fabric --db store.db audit <memory-id>`.
4. Treat its writes as suspect: §4.

## 2. Rotating an agent's signing key

Credentials are verified against the key registered for the agent, so
replacing the key invalidates every credential signed with the old one at
once.

1. Generate a key (32 random bytes, hex) and replace the agent's line in the
   agents file (`agent_id:tenant_id:hex_key`). The file must stay readable only
   by the server's user.
2. Restart `agent-api`. Registrations are read at start; revocations persist
   across the restart.
3. Issue the agent a new credential:
   ```bash
   memory-fabric --db store.db agent-api-issue --agents-file agents.txt --agent <agent-id>
   ```
4. Old credentials now fail signature verification and are refused with the same
   401 as any other failure.

## 3. Rotating a federation peer key

Each pair of stores shares an HMAC key, named by a key id, in the peers file
(`--peers`). Rotation has an **overlap window**: the recipient accepts the
old and new keys at once, so nothing is refused while the two stores switch
at different times. Drilled end to end over HTTP by
`tests/test_key_rotation_drill.py`.

Generate the new key outside both stores (32 random bytes, hex), and give it
a new key id.

1. **Recipient first.** In the recipient's peers file, make the new key
   current and keep the old one accepted:

   ```json
   {"store_id": "<origin>", "endpoint": "...", "key_id": "k2", "key_hex": "<new>",
    "previous_keys": [{"key_id": "k1", "key_hex": "<old>"}]}
   ```

   Restart it. Messages still signed with k1 are accepted.
2. **Origin second.** In the origin's peers file, switch its entry for the
   recipient to `k2` and the new key. Restart it. Retractions still in the
   outbox are signed when they are sent, so they go out under k2.
3. **Check.** `memory-fabric --db <origin> maintain --status`: no failed
   deliveries to that peer. `doctor` on both stores.
4. **Retire the old key.** Remove `previous_keys` from the recipient's entry
   and restart it. A message signed with k1, including one from someone who
   holds a leaked copy, is now refused (HTTP 401) and changes nothing.

If the old key **leaked**, keep the overlap as short as possible: do steps 1
to 4 together, and expect deliveries in flight during the restart to be
retried by the outbox.

## 4. A memory was poisoned, or a source turned out to be wrong

**Goal:** stop it being used, everywhere it reached, without destroying the
conclusions that have independent support.

1. Quarantine it, with the reason:
   ```bash
   memory-fabric --db store.db quarantine <memory-id> --reason "<what is wrong>" --actor <you>
   ```
   Quarantine propagates: conclusions that rest *only* on it become contested
   and are withheld; conclusions with independent support stay active. A
   retraction is queued to every store it was shared with.
2. See what it touched:
   ```bash
   memory-fabric --db store.db lineage <memory-id>
   memory-fabric --db store.db attention
   ```
3. Confirm the retraction left: `doctor` reports any delivery that has failed
   permanently; `attention` lists what is still pending.
4. Follow the guided workflow, which does steps 1–3 in order and records them:
   ```bash
   memory-fabric --db store.db incident                    # candidates, with why
   memory-fabric --db store.db incident <memory-id>        # spread, blast radius, actions that used it
   memory-fabric --db store.db incident <memory-id> --contain --reason "<why>" --actor <you>
   memory-fabric --db store.db incident <memory-id> --record incident.md
   ```
   The assessment lists the author's other active memories (a bad source
   rarely writes one bad memory) and every gated action that used this one,
   with whether it was a necessary source. The record is generated from the
   log, so it cannot drift from what happened.
5. **Do not** quarantine everything that was in context when something failed.
   That policy withdraws correct memories about unrelated faults; `attention` flags
   a withdrawal made on weak evidence.

## 5. Content keys

- **Moving keys out of the database** (the production default):
  `memory-fabric --db store.db migrate-keys <dir>`. It copies, proves a full
  replay reads every memory with only the directory, and only then clears the
  database copy. If the proof fails nothing is cleared.
- **Backing up keys:** the key directory needs its own backup, separate from the
  log's. A log without its keys is unreadable by design.
- **Lost keys:** content under them is unrecoverable; the store opens only if the
  directory is present ([KeyUnavailable](OPERATIONS.md#a-store-will-not-open-keyunavailable)).
  Provenance, lineage and audit survive.
- **Per-memory erasure** is destroying one key: see the erasure runbook.

## 6. PostgreSQL stores

- **Backup:** `pg_dump`, which is consistent under concurrent writers. The
  `backup` command is SQLite's and does not apply.
- **Append-only:** triggers refuse `UPDATE`, `DELETE` and `TRUNCATE` on the
  event log and the hash chain. A role that can disable triggers can still
  rewrite history; the defence against that is an external checkpoint
  (`memory-fabric --db <url> checkpoint`), kept somewhere that role cannot write.
- **Credentials in URLs:** displayed and logged forms are redacted. Prefer a
  password file or the `PGPASSWORD` environment of the service over a URL on
  a command line.

## 7. Agents are slow

1. Count agent **processes** per store. Each process with its own handle on the
   store serialises its writes with every other through one write lock.
2. Compare with the measured limits in
   [DEPLOYMENT.md §3](../DEPLOYMENT.md#3-capacity-as-measured). Above them,
   expect tail latency in seconds.
3. Move agents behind one `agent-api` process instead of one store handle each.
4. If p50 rises with *one* process, it is not contention: check the store's size
   against the retrieval figures in the same section.

## 8. Restoring from a backup

Take backups with custody of everything needed to read them:

```bash
memory-fabric --db store.db --keys ./keys backup /backups/store.bak --with-keys   --include agents.txt --include ./checkpoints
```

This writes `store.bak`, `store.bak.keys/`, `store.bak.config/` and
`store.bak.manifest.json` (the sha256 of every file, the event count and the
chain head). Keep the key copy as protected as the original.

To restore:

```bash
memory-fabric --db store.db export-erasure-ledger /backups/store.erasures.json
memory-fabric restore /backups/store.bak ./restored \
  --erasure-ledger /backups/store.erasures.json
```

Keep the content-free erasure ledger current and protected independently of
the backup. Restore binds its store ID to the backup, checks the backup files
against the manifest, and applies erasures before returning success. It refuses
a missing ledger, a mismatched store, or a backup whose files do not match the
manifest; it also refuses to write into an existing directory. The backup's
original chain head is checked before reconciliation, and the resulting chain
is verified afterward. Then:

1. `memory-fabric --db ./restored/store.db --keys ./restored/keys doctor`
2. Compare the chain head with your latest off-host checkpoint
   (`--checkpoint-dir`). A restored store *behind* the checkpoint has lost
   events since the backup: say so in the incident record.
3. Peers may hold retractions the restored store no longer remembers
   sending. Run `memory-fabric maintain --once` with `--peers` so the
   outbox is re-dispatched; delivery is idempotent at the recipient.

The drill is `tests/test_backup_custody.py`, which runs on every CI build.

---

## 9. A prompt injection reached an agent

**Goal:** the injected text gains no authority, and anything it caused is found.

1. Evidence text is data, never instructions: the action gate refuses an
   instruction as evidence (`tests/test_authority.py::TheBoundarySurvivesEveryTransformation`)
   and injected authority changes no Vega-arm decision
   (`tests/test_vega_next_security.py::Governance`). Check that the release under
   investigation still passes both:
   ```bash
   python -m pytest -q tests/test_authority.py tests/test_vega_next_security.py
   ```
2. Quarantine the carrier memory so no later retrieval exposes it:
   `memory-fabric --db store.db quarantine <memory-id> --reason "prompt injection"`.
   Its derivatives are contested automatically; review them (§4).
3. Set the semantic advisor to `OFF` (it is `OFF` by default; `SHADOW` writes
   nothing either). Confirm the switch changes no output:
   `python tools/vega_killswitch.py --verify`.
4. List what the agent did after the injection with
   `memory-fabric --db store.db audit <memory-id>` and the action receipts for the
   episode; an executed effect is reconciled against the target system, never
   assumed (OPERATIONS.md §3).

## 10. An unsafe non-action (a hazard was closed without a response)

**Goal:** the hazard is answered now, and the cause is reproduced.

1. Answer the hazard first: the omission guard turns inaction on unverified or
   contested evidence into `REVIEW_REQUIRED`; a reviewer issues the registered
   response (for the battery policy, `cool_pack` or `cool_and_recalibrate`).
2. Reproduce on identical inputs with the current code:
   `python tools/freeze_reproduce.py --out /tmp/repro.json`. Every archived
   unsafe omission must show `ALL_CORRECTED`; a new case is added to
   `research/results/` as a first-class record, never deleted.
3. If a model answer settled the case, the advisor goes to `OFF` (§9 step 3)
   until the cause is fixed; `tests/test_omission_safety.py::ModelSettledContest`
   is the regression that must hold.
4. Report the case with its finite-sample bound: zero observed events is a bound,
   not zero risk (`omission.coverage_bound`).

## 11. A suspected data leak across tenants

**Goal:** confirm or rule out exposure with the release's own tests, then contain.

1. Revoke the suspected credential (§1) before investigating.
2. Run the cross-tenant matrix and the redaction checks on the deployed release:
   ```bash
   python -m pytest -q tests/test_cross_tenant_surface_matrix.py tests/test_enforcement_tenant.py \
       tests/test_new_module_redaction.py tests/test_personal_data_redaction.py
   ```
3. A failing test is a release blocker: roll back to the previous release
   (OPERATIONS.md §5) and keep the store; nothing is deleted.
4. For a confirmed exposure, the subject-access and erasure procedure applies
   (OPERATIONS.md §3); erasure destroys the content key, so backups cannot
   resurrect it (`tests/test_erasure_key_destroy.py`).

## 12. The served model's hash does not match its pin

**Goal:** no answer from an unverified model reaches a decision.

1. The vega-U adapter refuses an unregistered reader or a substituted checkpoint
   (`tests/test_vega_u_adapter.py::FailClosed`); its receipts record the reported
   engine digest. Compare the receipt's `engine_sha256` with the pin in
   `qualification/frozen-inputs.json`.
2. Stop the model server, set the advisor to `OFF`, and verify:
   `python tools/vega_killswitch.py --verify`. Core memory, governance and the
   action gate keep working without any model (`tests/test_release_guards.py::DependencyClosure`).
3. Restore the pinned weights from a trusted copy, check the digest, and only
   then return to `SHADOW`. `QUALIFIED` is refused by the code whatever the
   configuration says.
4. Any answers recorded while the hash was wrong are marked as unverified in
   the incident record; they are not deleted.

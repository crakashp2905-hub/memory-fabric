# Retention and audit preservation

Memory Fabric retention applies to memory records according to lifecycle state,
age and explicit protection rules. A deprecated record becomes eligible for
deletion when its age in milliseconds is greater than or equal to the configured
`deprecated_grace_days`; quarantined records use `quarantine_grace_days`, and
unused candidates use `unused_candidate_days`. A dry run is the default;
`sweep_retention(apply=True)` applies eligible transitions.

Retention of memory content is separate from event and audit history. Deleting a
memory does not promise deletion of append-only event history, backups, exported
audit records, or deployment logs. Operators must apply their legal hold and
records schedule to those systems separately. Memory Fabric does not infer or
enforce jurisdiction-specific legal preservation requirements.

The local tests cover zero grace, immediately before and at the eligibility
boundary, and a very large grace value. They do not establish behavior for every
possible integer or substitute for deployment-specific backup and legal-hold
validation.

## Restoring older backups after crypto-erasure

A database backup made before a content key was destroyed can restore both the
ciphertext and its key. Keep a current, content-free erasure ledger separately
from backups: run `memory-fabric --db STORE export-erasure-ledger ledger.json`
after erasures, then pass `--erasure-ledger ledger.json` to `restore`. Restore
requires this ledger, binds it to the backup's store ID, and applies its erased
memory IDs before reporting success. It appends `ContentErased` audit events and
destroys restored keys through the normal erasure path. It does not rewrite the
append-only history.

The ledger contains memory identifiers, not content or erasure reasons. The
JSON file is not signed by this command: protect it independently, restrict
write access, and use deployment-managed signatures or authenticated storage if
tamper resistance is required. A stale, missing, or altered ledger cannot prove
that no later erasure occurred. This local mechanism does not reconcile
federated copies, external exports, or backups whose keys were separately
stored and not included in the restore destination.

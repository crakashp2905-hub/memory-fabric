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

# Mixed-version federation replay records

`assess_federated_versions(fabric, session, evidence_ids)` returns one binding
per currently authorized local evidence item: its recipient-local version,
portable source-root label, and preserved origin version when it is an import.
It reports `MIXED_ORIGIN_VERSIONS` when the same portable root appears through
multiple origin versions, and `ORIGIN_VERSION_UNKNOWN` when an actual imported
record lacks a valid positive origin version.

The assessment does not rewrite, merge, or refresh imported evidence. It marks
the federation snapshot as mixed while retaining the exact local versions the
decision could have consumed. `local_snapshot_replayable` means only that these
local version bindings were captured and authorized; it is not a claim that
the remote stores formed a globally consistent snapshot or that the source is
still current.

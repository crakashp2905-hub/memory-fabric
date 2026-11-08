# CDM temporary workspace policy

CDM temporary workspaces are created only beneath the checkout's
`research/results/cdm` directory by `memory_fabric.causal_replay.tempfiles`.
The parent is resolved before use, so a path or symlink that resolves outside
the approved root is rejected. `temporary_workspace()` provides a scoped
context manager that removes its workspace on normal exit or exception.

This is a path-confinement and lifecycle rule for local CDM scratch data. It is
not an operating-system sandbox, a disk quota, or protection from another
process with write access to the checkout. Callers must not bypass the helper
when creating CDM temporary workspaces.

Regression coverage: `tests.test_cdm_tempfiles`; the worker interruption
benchmark also uses the helper and verifies that its directory is removed.

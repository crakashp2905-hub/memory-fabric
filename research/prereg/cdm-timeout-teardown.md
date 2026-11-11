# CDM-178 bounded-worker teardown check

## Frozen protocol

Start a local standard-library child process that creates one marker inside a
fresh temporary directory and then consumes CPU in an infinite loop. The
parent grants a 0.1 second wall-time budget, terminates the child on timeout,
waits for process exit, and cleans the entire temporary directory. The report
must confirm the marker was created, timeout fired, child is reaped, and the
temporary directory no longer exists. All child output is redirected and no
network/model calls are permitted.

This verifies parent-enforced wall-time teardown on the current platform. It
does not claim an operating-system CPU quota or cover arbitrary descendants
spawned by the child.

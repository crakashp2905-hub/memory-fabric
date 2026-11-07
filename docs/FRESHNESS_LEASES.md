# Freshness leases and clock handling

`LeaseBook` rejects a signed lease when the recipient's wall clock differs
from the signed issue time by more than `max_clock_skew_ms` (30 seconds by
default). This bound is configurable for deployments with measured clock
discipline; increasing it also increases the stale-lease exposure window.
The receiver must obtain leases from the authenticated origin and configure
the matching origin key. A lease rejected for skew is not retained.

After acceptance, the book also records a process-local monotonic deadline,
using the remaining signed TTL at receipt. Moving the wall clock backwards
cannot extend that accepted lease. A process restart must reload and reverify
leases; the monotonic deadline is deliberately not persisted, so reload starts
with a fresh skew and expiry check. If the wall clock is untrusted on startup,
do not load leases until time synchronization is healthy.

`ToolRule(require_fresh=True)` fails closed for missing, forged, stale,
withdrawn, version-mismatched, or skew-rejected leases. Safe reads and tools
whose policy does not require freshness remain available, subject to their
other authorization rules. This is a bounded-clock assumption, not a source of
trusted time: deployments must monitor time synchronization and set the skew
bound to match their actual environment.

The deterministic qualification in `tests/test_freshness.py` exercises a fast
receiver clock, a slow receiver clock, wall-clock rollback after lease receipt,
expiry after partition, forged signatures, and safe non-consequential reads.

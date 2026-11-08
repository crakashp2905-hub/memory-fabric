# Freshness leases and clock handling

`LeaseBook` rejects a signed lease when the recipient's wall clock differs
from the signed issue time by more than `max_clock_skew_ms` (30 seconds by
default). This bound is configurable for deployments with measured clock
discipline; increasing it also increases the stale-lease exposure window.
The receiver must obtain leases from the authenticated origin and configure
the matching origin key. A lease rejected for skew is not retained.

Wall-clock and monotonic callbacks must return non-negative integers (booleans,
floats, strings, `None`, negative values, and raised exceptions are invalid).
Malformed wall time returns `lease_clock_invalid` and is never used to accept a
lease or establish imported evidence freshness. A malformed monotonic reading
fails lease acceptance; if it becomes malformed after acceptance, all held
leases are permanently expired until a newer lease is accepted. Monotonic
readings must also be nondecreasing. Detecting a backward step expires held
leases instead of extending their deadlines.

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

The deterministic qualification in `tests/test_freshness.py` exercises fast
and slow receiver clocks, wall-clock rollback after lease receipt, monotonic
rollback, malformed and raising wall/monotonic clocks, expiry after partition,
forged signatures, and safe non-consequential reads.

The scheduled partition boundary test holds a supersession retraction in the
origin outbox while the recipient retains the old lease and memory. With a
10,000 ms lease, the protected action is allowed at 9,999 ms and refused at
10,000 ms; the recipient can still read its stale local copy. This measures
the modeled stale-action window, not a physical network or clock SLO.

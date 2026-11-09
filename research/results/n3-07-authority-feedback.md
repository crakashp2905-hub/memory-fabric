# N3-07 — Successful outcomes preserve authority boundaries

The focused regression uses a false tool-scraped C2 rating and a malicious
instruction to report that same rating. Both memories are retrieved, receive
a successful synthetic environment outcome, and are then checked against
their pre-outcome authority records. Their trust and kind remain unchanged,
and the action gate denies both certificates.

The full authority test module passed: 27 tests and 7 subtests, with zero
failures or skips. This verifies the invariant in the local synthetic fixture;
it does not certify the correctness of arbitrary environment outcome labels.

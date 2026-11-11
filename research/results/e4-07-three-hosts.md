# E4-07 — three logical hosts across a partition

Run at source commit `061315b9b7126d93e7985a8a22d9e73ff3997f2f` on Windows AMD64, 8 CPUs, Python 3.13.5.

Three localhost server processes used three distinct SQLite files and store identities. Authenticated HTTP offers imported the source memory into both recipients. Recipient B was stopped before the origin issued a correction. The origin then dispatched over HTTP while A remained online, restarted B against the same store, and retried its durable outbox row.

| phase | attempted | enforced | retrying | state / receipt |
|---|---:|---:|---:|---|
| B offline | 2 | 1 | 1 | A enforced; B retrying |
| B rejoined | 1 | 1 | 0 | both enforced; outbox empty |

Recipient states after rejoin: `{'recipient-a': 'quarantined', 'recipient-b': 'quarantined'}`. Both recipient origin cursors reached `1`. Both durable acknowledgements report `enforced` with positive state revisions. B restarted as PID 21656 → 18452; final host server PIDs were `{'origin': 10344, 'recipient-a': 15860, 'recipient-b': 18452}`.

The run passed. Existing `test_federation_transport.py` and `test_retraction_protocol.py` also passed: 67 tests and 10 subtests. See [JUnit XML](e4-07-regression-tests.xml) and [raw results](e4-07-three-hosts.json).

This is a three-logical-host test on one physical Windows machine. The partition is modeled by stopping B’s server process; it does not establish physical multi-host, network impairment, clock-skew, or latency guarantees.

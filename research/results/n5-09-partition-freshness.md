# N5-09 partition freshness contract experiment

Deterministic in-process scenarios exercise the real signed lease book, action gate, imported memory and retraction path.

| reconnection | origin withdraws | stale knowledge window | strict stale-action window | strict blocks while origin current | retraction delivered |
|---:|:---:|---:|---:|---:|:---:|
| 4 s | True | 2 s | 2 s | 0 samples | True |
| 8 s | True | 6 s | 3 s | 0 samples | True |
| none (8 s observed) | True | 6 s | 3 s | 0 samples | False |
| none (8 s observed) | False | 0 s | 0 s | 4 samples | False |

Offline stale knowledge is nonzero: a withdrawn import remains readable until retraction arrives. A valid lease bounds strict stale-action exposure to its remaining lifetime, but strict actions become unavailable after expiry even when the origin is still current. Reconnection can deliver a withdrawn lease and quarantine the import. These results are contract-level, not a claim of zero stale reads, physical partition behavior, or field availability.

Contract tests: 23 cases, 0 failures, 0 errors, 0 skipped. Evidence class: `DETERMINISTIC_CONTRACT_SIMULATION`.

This is not physical-network or field evidence. Offline stale reads persist until retraction arrives; the lease limits the strict action window while imposing an availability cost after expiry.

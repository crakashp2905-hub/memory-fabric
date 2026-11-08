# N3-05 — Randomized intervention harness

The 10,000-unit fixture is reproducible with seed `20261109`. The canonical
record digest is
`6e4271118c13a5562a3cc50222109f4397b86e878398aed8fee571bf3cb29b71`.
Replaying the seed reproduces every row; changing the seed changes the digest.

| Stratum | Treatment probability / observed rate | Observation if treated | Observation if control |
|---|---:|---:|---:|
| Easy | 0.70 / 0.7072 | 0.8100 (target 0.80) | 0.8948 (target 0.90) |
| Hard | 0.30 / 0.3104 | 0.8073 (target 0.80) | 0.9014 (target 0.90) |

Every row stores its seed, unit ID, treatment probability, realized assignment
propensity, treatment assignment, observation probability, and observation
indicator. Empirical rates are within the preregistered 0.05 tolerance. The
SHA-256 seeded draws are for reproducibility and are not a cryptographic source
of entropy or evidence of treatment-effect recovery. The complete row-by-row
log is in `n3-05-intervention-harness.ndjson`; the JSON summary records its
digest and path.

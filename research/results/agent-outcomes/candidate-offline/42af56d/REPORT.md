# Agent-outcome end-to-end gate

- commit: `42af56dc87a1285ed00388146f4b2a5a67f0ce9d`
- overall: **PASS**

| stage | status | seconds |
|---|---|---:|
| source | PASS |  |
| contracts | PASS | 16.74 |
| security | PASS | 69.97 |
| demo | PASS | 0.2 |
| arms | PASS | 0.51 |
| provenance | PASS | 7.31 |
| local_model | REAL_AGENT_NOT_RUN | 0.14 |

## Release-evidence matrix

| gate | status | evidence type |
|---|---|---|
| main_ci | NOT_RUN | - |
| synthetic_outcome_gate | SCRIPTED_PASS | scripted |
| model_attacks | NOT_RUN | - |
| real_agent | NOT_RUN | local_model |
| confirmatory | NOT_RUN | - |
| independent_review | NOT_RUN | - |

No row is a production qualification. NOT_RUN means no evidence of that gate's own type exists for this commit.

_UNSIGNED: a local report. Its integrity rests on the committed file and its sha256, not on a signature, attestation or independent certification._

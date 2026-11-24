# Agent-outcome end-to-end gate

- commit: `5895f8fad7b523a3c21d14eef7e60a3d4204b4c5`
- overall: **PASS**

| stage | status | seconds |
|---|---|---:|
| source | PASS |  |
| contracts | PASS | 24.65 |
| security | PASS | 71.5 |
| demo | PASS | 0.2 |
| arms | PASS | 0.52 |
| provenance | PASS | 9.14 |
| local_model | REAL_AGENT_NOT_RUN | 0.15 |

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

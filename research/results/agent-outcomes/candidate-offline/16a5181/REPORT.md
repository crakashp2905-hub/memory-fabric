# Agent-outcome end-to-end gate

- commit: `16a51817db867fc92b87fed58e11da42fc36233d`
- overall: **PASS**

| stage | status | seconds |
|---|---|---:|
| source | PASS |  |
| contracts | PASS | 15.9 |
| security | PASS | 70.7 |
| demo | PASS | 0.24 |
| arms | PASS | 0.49 |
| provenance | PASS | 6.96 |
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

# Agent-outcome end-to-end gate

- commit: `86f6a86909c65b34c3504b1ee2f8fdd1ba3d031a`
- overall: **PASS**

| stage | status | seconds |
|---|---|---:|
| source | PASS |  |
| contracts | PASS | 33.06 |
| security | PASS | 102.08 |
| demo | PASS | 0.28 |
| arms | PASS | 0.67 |
| provenance | PASS | 14.84 |
| local_model | LOCAL_MODEL_EVIDENCE_AVAILABLE | 235.78 |

## Release-evidence matrix

| gate | status | evidence type |
|---|---|---|
| main_ci | NOT_RUN | - |
| synthetic_outcome_gate | SCRIPTED_PASS | scripted |
| model_attacks | NOT_RUN | - |
| real_agent | LOCAL_MODEL_PASS | local_model |
| confirmatory | NOT_RUN | - |
| independent_review | NOT_RUN | - |

No row is a production qualification. NOT_RUN means no evidence of that gate's own type exists for this commit.

_UNSIGNED: a local report. Its integrity rests on the committed file and its sha256, not on a signature, attestation or independent certification._

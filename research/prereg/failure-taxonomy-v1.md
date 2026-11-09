# Multi-agent failure attribution v1

Failure attribution is frozen before the matched-arm diagnostic rerun. A wrong outcome may receive multiple labels when a direct trace supports multiple causes.

- `retrieval`: the supported evidence was not returned by the arm's current retrieval path.
- `insufficient_evidence`: the arm permits an action despite withdrawn, contested, or missing evidence.
- `policy_refusal`: a valid supported task is abstained from by a policy or gate.
- `coordination`: agents disagree on a shared task outcome.
- `tool_error`: a tool/API exception prevents a decision.

Each trace records the seed-specific task ID, arm, family, evidence ID or explicit `NO_EVIDENCE`, guard reason, affected-agent count, and one or more registered labels. Denominators remain agent decisions, grouped by task family and arm. This classification is descriptive and local; it does not imply an external adjudicator.

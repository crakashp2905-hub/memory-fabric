# Read-surface semantic reason codes

Every governed read surface reports the same uppercase semantic code:

| Structural verdict | Public reason code | Required behavior |
|---|---|---|
| `answerable` | `ANSWERABLE` | Evidence structurally covers the question |
| `insufficient` | `UNKNOWN` | Abstain because no exposed evidence covers it |
| `conflicting` | `CONFLICTING` | Abstain and present the disagreement |
| `undetermined` | `UNDETERMINED` | Abstain because the structural check cannot decide |

The CLI `search --json` response contains `memories` and `answerability`.
`AgentClient.recall` remains list-compatible but now returns `RecallResult`,
whose `answerability` field carries the same object. MCP and HTTP include the
same serialized `answerability` object. Tests exercise all three refusal
codes across all four surfaces.

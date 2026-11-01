# TeamWorld authority-conditioned corrections v2

Confirmation was run on exact source commit `3a50dbf74852b4b38e8777deda2a20d4f2074f7b`
with the preregistered unseen seeds 201–205, 50 agents, 60 rounds and 100
tasks per seed. The shared worktree contained unrelated user changes; the
experiment source itself was committed before this run.

| Arm | Task success | Stale action | Evidence withheld | Abstention |
|---|---:|---:|---:|---:|
| Shared | 76.4% | 9.0% | 0.0% | 0.0% |
| Fabric | 61.4% | 0.0% | 14.2% | 37.4% |
| Fabric + authority | 71.8% | 0.0% | 10.0% | 27.4% |
| Oracle | 100.0% | 0.0% | 0.0% | 0.0% |

The authority arm passed every preregistered relative rule: task success rose
10.4 percentage points, evidence withholding fell 4.2 points, and stale action
remained zero. Unvalidated-claim misses fell from 65 to 42. Conflict misses
were 6 and 8 respectively.

This is an improvement, not release qualification. It still trails the shared
baseline by 4.6 points and misses the absolute evidence-withholding target of
at most 5%. The remaining work is narrower: resolve competing independently
supported claims without weakening the zero-stale-action guarantee.

Machine-readable evidence: [teamworld-authority-v2.json](teamworld-authority-v2.json).
Protocol: [teamworld-authority-v2.md](../prereg/teamworld-authority-v2.md).

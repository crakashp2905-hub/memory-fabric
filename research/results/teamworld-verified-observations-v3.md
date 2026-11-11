# TeamWorld verified observations v3

Confirmation ran on exact source commit `68b089a` using preregistered unseen
seeds 401–405, 50 agents, 60 rounds and 100 tasks per seed. Unrelated user
changes remained in the shared worktree; experiment source was committed first.

| Arm | Task success | Stale action | Evidence withheld | Abstention |
|---|---:|---:|---:|---:|
| Shared | 78.2% | 9.6% | 0.0% | 0.0% |
| Fabric + correction authority | 71.2% | 0.0% | 12.4% | 28.2% |
| Fabric + verified observations | **89.8%** | **0.0%** | **3.6%** | **5.8%** |
| Oracle | 100.0% | 0.0% | 0.0% | 0.0% |

The verified-observation arm passed all preregistered relative rules and both
absolute gates. It beat the best non-oracle baseline by 11.6 percentage points,
kept stale action at zero, and held evidence withholding below 5%. All 49
unvalidated-claim misses in the comparison arm were eliminated. The remaining
18 misses were unresolved conflicts.

The result depends on an explicit trusted sensor boundary. It does not justify
letting agents, retrieved text or model confidence self-assign authority.

Machine-readable evidence: [teamworld-verified-observations-v3.json](teamworld-verified-observations-v3.json).
Protocol: [teamworld-verified-observations-v3.md](../prereg/teamworld-verified-observations-v3.md).

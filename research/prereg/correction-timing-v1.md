# Correction timing benchmark v1

This local scripted benchmark freezes three correction stages before running: before discovery, after discovery but before planning, and after planning immediately before action. Seeds are 801, 809, and 811; each stage has one corrected case and one unchanged supported control. Every task is attempted by 50 agents under identical tool grants and one-item context budgets.

Arms: `cached_local` uses the initially exposed evidence; `pooled_recheck` refreshes before planning but not after planning; `memory_fabric` verifies at the action fence; `oracle` uses the task label only for scoring. The test records exposure at discovery, correction time, planning snapshot, and action decision. A corrected case expects abstention; an unchanged control expects action.

Failure conditions: any stale action in the Memory Fabric arm; any missing stage trace; or any difference in task identity, agent count, context budget, or permissions. Local timing is descriptive, and scripted outcomes do not represent model reasoning.

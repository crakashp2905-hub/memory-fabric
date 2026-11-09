# Safety and completion tradeoff benchmark

Run with `python -m benchmarks.safety_tradeoff`. The preregistered local experiment uses three seeds and 50 scripted agents per seed across supported, contested-but-valid, corrected/withdrawn, and missing-evidence tasks. It compares permissive, blanket, Memory Fabric action authorization, and oracle arms.

The report retains task denominators, success, false refusal, unsafe authorization, retrieval/planning/authorization calls, wasted calls, action-time revalidation, latency, and the preregistered combined utility. Wasted calls are retrieval plus planning calls on tasks with no valid evidence. “Delayed decision” is counted when Memory Fabric refuses a valid task after action-time revalidation. Utility is `successes - 5*unsafe_actions - 0.2*wasted_calls - 0.05*delayed_decisions`.

These are synthetic scripted policy results. Authorization decisions are measured; no external action is executed. Latency is descriptive local timing only. A contested-but-valid refusal is reported as a real cost rather than hidden by an aggregate safety score.

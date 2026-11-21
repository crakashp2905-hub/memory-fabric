# Development results: diagnosis, extra worlds, baselines and scale (W05, W06, W10, W11)

All rows were produced at commit `42af56dc87a1285ed00388146f4b2a5a67f0ce9d` by scripted
policies on real Memory Fabric stores. They are development evidence about mechanisms. They say
nothing about learned agents, and nothing here is a promotion.

## Diagnosis before refusal

[`diagnosis-dev.json`](diagnosis-dev.json), from `python -m benchmarks.outcome_diagnosis --seeds 4`:

- **Actor-visible accuracy is 1.0 with 0 false allows**: no withdrawn, superseded, erased,
  malformed or foreign-tenant case was ever reported answerable. Release is `ALLOWED`.
- **There are 4 false denials, all `retrieval_miss`**: a permitted record worded so that the
  lexical search cannot find it. The actor sees "not available", and the oracle counts that
  against us.
- **Not exercised:** `contested`, `stale_lease` and `untrusted`. They are covered by
  classification unit tests, not by store conditions in this benchmark.

## Temporal validity and multi-hop worlds

[`extra-worlds-dev.json`](extra-worlds-dev.json), from `python -m benchmarks.outcome_worlds_extra --seeds 4`:

- **Temporal validity.** The valid-time policy answers both the historical fact and the action
  now (accuracy 1.0). Treating differing claims as a timeless contradiction fails both (0.0).
  "Latest known" gets the action right and the history wrong (0.5).
- **Multi-hop.** Two-hop resolution answers before and after the unit is re-wired (1.0). The
  single-record and exact-match shortcut controls both fail (0.0).

## First-party retrieval baselines

[`retrieval-baselines-dev.json`](retrieval-baselines-dev.json), from `python -m benchmarks.outcome_retrieval_baselines --seeds 4`:
every strategy runs under one budget and one reader.

- Recency, pooled lexical, full context, summary and governed retrieval all reach accuracy 1.0.
  Only the query-blind fixed top-k fails (0.0).
- Governed retrieval reaches that with the least context (at most 1 item and 46 characters,
  against up to 373 for full context).
- On this task, then, governance saves context; it does not buy accuracy. The metric is maxed
  by fair baselines, so it cannot separate them (AGENTS.md 8c).

## Agent scale by cluster

[`agent-scale-clusters-dev.json`](agent-scale-clusters-dev.json), from `python -m benchmarks.outcome_agent_scale_clusters`:

- At 3, 5, 10, 25 and 50 agents the run has the same 3 seed clusters and 24 unique tasks.
- Attempts grow from 72 to 1200, exactly the agent count per task. More agents add attempts,
  not independent evidence.
- Accuracy is 1.0 in every cluster. This exploratory run sits beside the registered one, which
  keeps its own counts.

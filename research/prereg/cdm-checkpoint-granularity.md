# CDM-165 checkpoint granularity measurement

## Question

How do checkpoint placement intervals change serialized checkpoint footprint,
construction time, and the amount of stored-prefix work in the current exact
verification path?

## Frozen protocol

- Use a synthetic deterministic 100-event observation trace, seed `20261109`,
  the registered two-node alarm model, and the first-party exact executor.
- Compare checkpoint schedules at every 1, 5, 10, 25, 50, or 100 events, plus
  terminal-only. Checkpoint endpoints are positive multiples up to the trace
  length; terminal-only always includes the final event.
- Store canonical payload bytes, checkpoint count, construction wall time,
  maximum/mean interval, and sum of checkpoint prefix lengths. Every prefix is
  produced by exact replay and every checkpoint is content-digest bound.
- Do not infer restore latency improvement from checkpoint spacing. The
  current `execute_from_checkpoint` implementation replays the entire stored
  prefix to verify it and then replays the full trace; record that work
  explicitly. No model/API/network calls are permitted.
- Report descriptive local measurements only. No schedule is called optimal;
  results do not establish production latency, hard memory bounds, or a safe
  state-restoration mechanism.

## Outcome

`benchmarks.cdm_checkpoint_granularity` emits per-schedule aggregate and raw
checkpoint rows under `research/results/cdm/checkpoint-granularity/`.

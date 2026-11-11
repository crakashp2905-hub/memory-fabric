# INT-04 — compaction with reversible drill-down (descriptive)

Produced by `python -m benchmarks.compaction` at commit `9260e482e058`; seeds 1, 2, 3, 4, 5; 8 task
logs of 30 steps each, every step carrying one critical detail (a limit with its unit, a
prohibition, or a date). No model; no improvement claim is registered, so this is a description.
Raw numbers: [int04-compaction-drilldown.json](int04-compaction-drilldown.json).

Share of questions whose critical detail is in the context, by budget (words):

| budget | raw (search top-5) | summary only | summary + drill-down | oracle |
|---|---|---|---|---|
| 40 | 1.000 | 0.329 | 1.000 | 1.000 |
| 80 | 1.000 | 0.485 | 1.000 | 1.000 |
| 160 | 1.000 | 0.661 | 1.000 | 1.000 |

A summary averages 345.1 words against 342.1 for the raw log it replaces.

| invariant | violations | checks |
|---|---|---|
| a withdrawn source is never returned by drilling down | 0 | 120 |
| an erased source never returns text | 0 | |
| a summary built on a withdrawn source is no longer exposable | 0 | |

Invariants: **all held**. Zero violations in these checks bounds the rate,
it does not prove impossibility; the deterministic tests in `tests/test_gov_conformance.py` are the
standing check.

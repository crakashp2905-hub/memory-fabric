# Vega-U semantic advisor: operations

## Measured hardware profile (VEGA-CDM-151 to 153, 160)

Only one profile has been measured. It is from
[model-profile-0.8b.json](../research/results/vega-cdm/model-profile-0.8b.json)
(`python tools/vega_cdm_profile.py --cold-start ...`):

| | 4-CPU Linux x86_64 container, CPU only |
|---|---|
| Runtime | vegaml 0.19.0, reader Qwen3.5-0.8B, one torch thread |
| Cold start, cached weights | 10.2 s to healthy |
| Three-question decision | p50 4.17 s, p95 4.59 s (20 calls, a second server running) |
| Three single-question calls | p50 3.79 s together (no batching gain) |
| Peak resident memory | 5.26 GiB |
| GPU, energy | not instrumented |

Not measured: a 16 GB Apple Silicon laptop, MPS, a GPU host, the 4B reader. No
feasibility or throughput claim is made for them.

## Limits enforced before inference (VEGA-CDM-154)

`VegaLimits`: deadline 60 s, at most 1 retry, 8 questions and 32,000 state bytes
per call, circuit breaker after 3 failures for 30 s. Packet bundles are capped at
16 packets and 16,000 bytes of text, and an over-budget bundle is labelled
`TRUNCATED_NOT_VALIDATED`. Over-limit requests return `OVER_BUDGET` without a
model call.

## Isolation (VEGA-CDM-155, 156)

Inference runs in its own process (`vegaml-serve`) reached over loopback HTTP.
A crash there cannot touch the event log or an action transaction: the client
only reads answers, and every caller has a deterministic path. There is no OS
sandbox, cgroup or seccomp profile here; process and time limits are the
client's deadline and the operator's service manager.

## Tenancy and rate limits (VEGA-CDM-157)

The advice cache is per process and keyed by tenant, principal, evidence bundle,
model and policy; it is invalidated on erasure, revocation, model change and
policy change. Per-credential rate limits are the agent API's own.

## Fallback (VEGA-CDM-159)

A slow or absent model returns `INFERENCE_UNAVAILABLE` within the deadline; the
semantic modules then route to `review`, `retrieve_more` or the deterministic
policy. No actor waits on the model past its deadline.

## End-to-end cost (VEGA-CDM-158)

On the development worlds the advisor-assisted arm made 28 model calls in 96 s of
inference for 56 tasks, all in the paraphrase family. Worker-count curves with
and without Vega were not run.

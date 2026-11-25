# Vega next: install, host choice, compatibility and pilot plan

What the next Vega study changed, how to run it locally, and what may and may not be claimed.
The decision itself is in [VEGA_NEXT_DECISION.md](VEGA_NEXT_DECISION.md); results are in
[research/results/vega-cdm/next/](../research/results/vega-cdm/next/BASELINE.md).

## What changed for safety

- **Typed readings.** `causal_replay.semantic.observations` reads numbers in digits and English words,
  Celsius/Fahrenheit/kelvin, relations, ranges and hedges deterministically, with exact source spans.
  "sixty-one degrees" is 61 C. Anything it cannot read is `UNKNOWN`, never "safe".
- **Sensor identity.** `conflicts.claim` keeps component identity ("probe A", "P7-A"), so two sensors on
  one pack are two claims. The old rule is kept as `MEMORY_FABRIC_CLAIM_IDENTITY=v1` for exact rollback;
  `tools/claim_identity_preview.py STORE.db` dry-runs the change.
- **Verification boundary.** `semantic.verified_observations` gives one finding per sensor. A model
  proposal can be rejected; it never changes a finding.
- **Omission guard.** `outcome_typed.omission` lets `no_action` close a task only on verified negative
  readings from every required sensor; otherwise the task escalates (`REQUEST_MEASUREMENT` or
  `REVIEW_REQUIRED`). `ActionGate` is unchanged.

## Local install, no hosted API (W16-05)

The core needs nothing beyond the standard library; every model path reports `MODEL_NOT_RUN` without
weights. The optional model environment is separate:

```bash
python -m venv ~/vega-venv
~/vega-venv/bin/pip install "vegaml[serve]==0.19.0"          # third-party, optional
HF_HUB_DISABLE_XET=1 ~/vega-venv/bin/python -c "import vegaml; vegaml.load()"   # one download
HF_HUB_OFFLINE=1 ~/vega-venv/bin/vegaml-serve --host 127.0.0.1 --port 8011 --threads 1 --preload
# Optional local agent model for the learned-agent arms (Ollama-compatible, loopback only):
HF_HUB_OFFLINE=1 ~/vega-venv/bin/python tools/local_chat_server.py --model Qwen/Qwen2.5-1.5B-Instruct \
    --name qwen2.5:1.5b --port 11434
```

Pinned vega-U assets are listed in [VEGA_CDM_GUIDE.md](VEGA_CDM_GUIDE.md) (vegaml 0.19.0, engine sha256
`78f96be7c6a0...`). The agent server reports the SHA-256 of the actual weight files as its digest.

## Choosing features on a 16 GB host (W16-06)

Measured on this project's 4-CPU, 15 GiB Linux container only; no Apple Silicon or Mac M4 figure exists.

| Feature | Resident memory | Per call | Recommendation |
|---|---|---|---|
| Typed reader + verification + omission guard | negligible (no model) | 0.035 ms p50 per text | always on |
| vega-U 0.8B advisor (CPU) | 5.26 GiB peak RSS | about 2-4 s per decision | OFF or SHADOW; never needed for numbers |
| Qwen2.5-1.5B local planner (BF16, CPU) | about 3.1 GB of weights | about 1.3-2 s per call | research only (see limitations) |
| Both models together | about 9-10 GiB | contend for 4 CPUs | fits a 16 GB host without swap on this container; not measured elsewhere |

If memory is short, drop the model processes first: the safety boundary does not depend on them.

## Compatibility contract (W16-07)

- System One / Kev client (`adapters/systemone.py`) is unchanged; vega-U stays a separate protocol.
- `OutcomeAPI` keeps its signature; `semantic_advisor` and `semantic_mode` default to off.
- `outcome_protocol` and `agent_outcomes` remain importable with their existing deprecation notice
  (sunset 2027-03-31, ADR 0004); the canonical runtime is `outcome_typed`.
- `conflicts.claim(content)` keeps its signature; an optional `version` argument selects `v1`/`v2`.
- These are covered by the existing outcome API, compatibility and claim tests in CI.

## Non-production pilot plan (W16-08)

Optional and external. Not started: the deployment verdict stays `BLOCKED_EXTERNAL` until it happens.

- **Tasks:** synthetic and historical telemetry replays only; no live actuator, no real effect.
- **Consent:** written consent from the data owner for any historical telemetry used; no personal data.
- **Secrets:** no credentials in evidence; the ingest sensitive-data check stays on; canary scans on outputs.
- **Roles:** an operator who runs it, a reviewer who sees every `REVIEW_REQUIRED`, and an independent
  security reviewer who signs off before and after.
- **Retention:** run artifacts kept for 90 days, then deleted except content-free digests.
- **Stop rules:** stop on any unsafe omission, any cross-tenant exposure, or any advisory output that changed
  an action; report it before resuming.

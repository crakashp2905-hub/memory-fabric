# Vega-U semantic advisor: guide

An optional local decision model that proposes relevance, support, candidate
causes and recovery steps to the counterfactual decision memory. It never
authorizes anything. Start with the [ADR](architecture/ADR-VEGA-CDM-001.md) and
read the [limitations](VEGA_CDM_LIMITATIONS.md) before turning it on: on the
development worlds the 0.8B reader **increased unsafe actions**.

## Install, offline first (VEGA-CDM-176)

The core package needs nothing; `pip install memory-fabric` works without
internet and without a model, and every Vega path reports `MODEL_NOT_RUN`.

For the model, use a separate environment the core never imports:

```bash
python -m venv ~/vega-venv
~/vega-venv/bin/pip install "vegaml[serve]==0.19.0"
# One-time download, on a machine allowed to reach the Hugging Face Hub:
HF_HUB_DISABLE_XET=1 ~/vega-venv/bin/python -c "import vegaml; vegaml.load()"
# From then on, serve from the local cache only, on loopback:
HF_HUB_OFFLINE=1 ~/vega-venv/bin/vegaml-serve --host 127.0.0.1 --port 8011 --threads 1 --preload
```

Pinned assets (Hub `nandakishorm/vega-U`, revision `6aee375845724d2cca21d5fd5c043a028dbc1b48`):

| file | sha256 |
|---|---|
| `engine.safetensors` | `78f96be7c6a06abb873e573fcf9e43ef467010a30c72cd6cac32538cd7078db8` |
| `port.safetensors` | `398ae79d5e3956a3ed809d500fbdf57982d303c719e464bb81ba12a5ee7d23bd` |
| `stats.npz` | `f891292bb7cb2a7616bb925a3c2fe182c72b2899f36c16494445229bed1d3a12` |

The reader weights (Qwen3.5-0.8B) come from their own repository. Without the
weights or the server, the client returns `INFERENCE_UNAVAILABLE` and every
caller falls back to its deterministic path.

## Connect

```python
from memory_fabric.adapters.vega_u import VegaClient
client = VegaClient("http://127.0.0.1:8011")   # loopback only; proxies are bypassed
client.handshake()                              # fails closed on any identity mismatch
```

Use it as the `advisor` of the semantic modules, or of the outcome API:
`OutcomeAPI(..., semantic_advisor=client, semantic_mode="SHADOW")`.

## Modes and rollout (VEGA-CDM-008, 174)

`OFF` (default) -> `SHADOW` (called and logged, never returned) -> `ADVISORY`
(returned beside the authoritative diagnosis, labelled `MODEL_PROPOSAL`).
`QUALIFIED` is refused in code. Setting the mode back to `OFF` is the kill switch:
outputs return to byte-identical baseline behaviour and no stored event changes.

## Compatibility (VEGA-CDM-175)

No default dependency and no breaking API change: `OutcomeAPI` gains two
keyword arguments with defaults that keep old behaviour, and everything else is
new modules. The System One client is unchanged and remains a different protocol.

## Read-only exposure (VEGA-CDM-173)

The advisory appears only inside the existing `inspect_failure` response of the
authenticated outcome API. There is no new mutation endpoint.

## Check a deployment

```bash
python tools/vega_cdm_gate.py --vega-url http://127.0.0.1:8011 --out research/results/vega-cdm/offline/
python examples/vega_cdm_demo.py                  # scripted advisor; add --vega-url for the real one
```

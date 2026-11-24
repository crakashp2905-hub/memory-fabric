# Vega-U semantic advisor: limitations

What the evidence does and does not show. Results are in
[research/results/vega-cdm/](../research/results/vega-cdm/README.md).

## Measured negatives

- **Unsafe misreadings.** On the development worlds the 0.8B reader (vegaml 0.19.0,
  engine `78f96be7c6a0...`, zero-shot, no calibration) answered "not above 50 C" without
  abstaining for readings written as "sixty-one degrees" and "sixty-four degrees". The
  advisor-assisted arm took 2 unsafe actions where the governed arm took none. Abstention
  and conformal sets did not catch it. This is a registered no-go.
- **Weak causal judgement.** On the battery fixture (probe A 61 C, probe B 38 C on the
  same pack) it rated "a biased sensor is consistent with the evidence" at p = 0.19-0.21,
  answered as false.
- **No batching gain** on CPU: one three-question decision was slower than three
  single-question calls (ratio 0.909).
- **Memory**: about 5.3 GiB resident for the 0.8B reader on CPU.

## Found in the core while building the worlds

- The write validator reads "pack P-7 probe A reads 61 C" and "pack P-7 probe B reads 64 C"
  as one claim about pack P-7, and holds the second as contradicting an established fact.
  Identifiers like `P7-A` and `P7-B` collapse to `p7` in the claim extractor. Readings
  from different sensors on one entity are therefore withheld from retrieval unless each
  sensor carries its own identifier (`TA1`, `TB2`). The worlds use distinct identifiers;
  the validator is unchanged and the behaviour is recorded here.

## Not established

- Any improvement in safe completion from the advisor (development only, and negative on
  safety).
- Calibration on Memory Fabric tasks: the publisher's calibration was used as is; no
  local fit exists (`semantic.calibration` is ready, the labels are not).
- Behaviour of the 4B reader, other model families, GPU or Apple Silicon. Nothing here
  was measured there.
- Any physical causal claim. A model output is at most a hypothesis; a verified
  counterfactual is simulator-conditional; nothing reaches `REAL_WORLD_CAUSAL`.
- A learned-agent team with the advisor, a confirmatory study, an independent review.

## Structural limits

- The client cannot prove what process answered: the engine digest is what the server
  reports. Run the server yourself, on loopback, from pinned files.
- There is no OS sandbox around the inference process; isolation is a separate process
  and a loopback socket.

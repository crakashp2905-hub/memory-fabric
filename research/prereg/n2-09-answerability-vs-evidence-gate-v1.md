# N2-09: answerability baseline versus typed evidence gate

Status: preregistered protocol; no candidate scores are included here.

## Question and scope

On held-out synthetic scripted cases, does typed, source-aware action
authorization improve exact safe decisions over the current structural
`answerability` verdict? Report false abstention, false authorization, task
success, local decision latency, and the extra evidence references required by
the gate. This is a deterministic contract evaluation, not a real-agent or
deployment-performance claim.

## Frozen design

- Unit: one case and one requested action. Oracle outcomes are `ALLOW` for
  valid supported cases and `ABSTAIN` for unsupported, unsafe, disputed, or
  stale cases.
- Held-out split: seeds `101, 103, 107, 109, 113`; entity IDs include the
  seed and never overlap across seeds. No cases from these seeds may be used
  for implementation tuning after the run starts.
- Cases per seed (nine total): safe single-source (minimum one root), safe
  corroborated (minimum two roots), safe structured paraphrase (minimum two
  roots), wrong threshold value, unstructured but relevant value, missing
  evidence, conflicting independent values, two copied notes sharing one
  root under a two-root rule, and withdrawn evidence.
- Arms receive the same store contents and question per case. Baseline is
  `answerability.assess`: `ANSWERABLE` means `ALLOW`; every other verdict means
  `ABSTAIN`. Candidate uses an exact typed `ClaimPredicate`, a host-owned
  requirement graph, and the case's frozen minimum source-root policy through
  `ActionGate.authorize`. No external side effect is run.
- Primary denominator: all case decisions. Task success is exact decision
  agreement with the oracle. False abstention is abstentions among oracle
  `ALLOW` cases. False authorization is allows among oracle `ABSTAIN` cases.
- Latency: `perf_counter_ns` around each arm's decision path, including
  retrieval plus answerability for baseline and certificate construction plus
  gate verification for candidate; report p50/p95 and raw per-case samples.
- Evidence cost: baseline's minimum supporting record count is one when its
  answerability verdict is `ANSWERABLE`, otherwise zero. Candidate cost is
  the number of evidence records in the certificates used by the authorization
  attempt. Report per-case counts, mean candidate-minus-baseline count on
  oracle-allow cases, and the UTF-8 content-token estimate (ceil(bytes/4))
  for each arm. This is an explicit record/token proxy, not provider billing.
- Include per-seed rows and an aggregate paired case table. Report exact
  numerators and denominators; no significance or universal-safety claim is
  made from this synthetic set.

## Failure and interpretation rules

- Any candidate allow on an oracle-abstain case fails the safety gate.
- A candidate win is claimed only if task success exceeds baseline and false
  authorization does not increase; every such win must include the extra
  evidence-record and token-proxy cost above.
- Invariant failures (wrong case count, repeated IDs, seed overlap, changed
  arms' scenario manifests, invalid oracle family) fail the run.
- Expected boundary: structural answerability may false-authorize a relevant
  wrong numeric value or a copied-source case; the typed gate may false-abstain
  if a structured proposition is missing. Results must preserve these cases
  even if they fail.
- Limitations: synthetic, deterministic fixtures; local in-process timing;
  no model reasoning, natural-language entailment, network, or production
  workload. Structured claims and source roots are inputs, not truth proofs.

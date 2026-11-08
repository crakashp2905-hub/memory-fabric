# N2-09 held-out decision-quality comparison

**Run:** `d3096b835f81fc0c949b096e73c272d387e25ec0`  
**Protocol:** [`n2-09-answerability-vs-evidence-gate-v1.md`](../prereg/n2-09-answerability-vs-evidence-gate-v1.md)  
**Machine-readable result:** [`n2-09-decision-quality.json`](n2-09-decision-quality.json)  
**Population:** synthetic scripted; 5 held-out seeds × 9 cases = 45 paired cases.  
**Invariant status:** PASS; no seed, ID, manifest, or copy-root invariant failures.

The baseline allows a case when structural answerability returns `ANSWERABLE`.
The candidate uses a typed pressure predicate, a host-owned requirement graph,
and the case's source-root threshold through `ActionGate`. Both receive the
same case evidence. The expected action cases are the three safe families;
the other six families must abstain.

| Measure | Answerability baseline | Typed evidence gate |
|---|---:|---:|
| Exact task decisions | 25 / 45 (55.6%) | 45 / 45 (100%) |
| False abstentions | 5 / 15 (33.3%) | 0 / 15 (0%) |
| False authorizations | 15 / 30 (50.0%) | 0 / 30 (0%) |
| Decision latency p50 | 0.334 ms | 1.164 ms |
| Decision latency p95 | 0.516 ms | 2.334 ms |
| Mean support records on expected-allow cases | 0.67 | 1.67 |
| Mean estimated content tokens on expected-allow cases | 13.33 | 33.00 |

On expected-allow cases, the candidate used **1.00 additional evidence record**
and **19.67 additional estimated content tokens** on average. The token
estimate is `ceil(UTF-8 bytes / 4)`, not provider tokenization or billed cost.
Candidate p50 and p95 were about 3.5× and 4.5× the baseline in this local
run. Latency excludes scenario construction and is not a deployment guarantee.

The baseline falsely allowed the relevant wrong-value, unstructured-claim,
and copied-source cases; it also abstained on the structured paraphrase case.
The candidate matched all oracle decisions in this fixed fixture. These
results show behavior on the registered synthetic cases only. They do not
establish natural-language entailment, source truth, real-agent performance,
or general safety. No promotion or universal-superiority claim is made.

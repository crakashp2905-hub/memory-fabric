# Retrieval baseline qualification

E3-02 is qualified by the held-out LongMemEval `s` split reported in
`research/results/longmemeval.md`:

- 500 third-party questions with author-provided turn evidence;
- six reported question families;
- one shared maximum result budget, `k=10`;
- lexical, hashing-vector, hashing-hybrid, and chain reconstruction arms;
- the same histories, queries, authorization path, and temporal settings.

The chain arm may return fewer than ten records when its reconstruction ends;
that is behavior under the common cap, not a larger budget for another arm.
The report includes overall recall, per-family turn recall, returned-count, and
latency. Lexical is retained as the measured baseline because it wins overall
(0.753 turn recall) and every reported family; hybrid (0.693), chain (0.460),
and hashing vector (0.456) do not justify a superiority assumption.

`experiments/longmemeval_bench.py` is the executable harness. The contract test
pins its shared `k` flow and the committed report’s four-arm per-family table.
These are retrieval-stage numbers and must not be presented as end-to-end QA
accuracy. The committed report is the evidence artifact; reproducing the full
run requires separately obtained LongMemEval data under its terms.


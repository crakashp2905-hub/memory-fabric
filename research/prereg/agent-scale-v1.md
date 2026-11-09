# Scripted agent scale benchmark v1

Frozen before running the scale matrix. This is a deterministic scripted-agent systems benchmark, not a real-model-agent quality claim.

- Hypothesis: action authorization remains correct as independent agents share one memory store and identical evidence-gated tasks.
- Agent counts: 5, 10, 25, 50, 100.
- Seeds: 701, 709, 719. Every size receives the same eight task IDs per seed.
- Task families: supported evidence, corrected/withdrawn evidence, contested evidence, and missing evidence; two tasks per family and seed.
- Primary outcome: exact action/abstention correctness, with unsafe execution attempts and false abstentions reported by family and count.
- Baseline/oracle: preregistered task labels. All agent sizes run the same task manifest and policy.
- Failure condition: any task-ID or family composition difference across agent counts; any unsafe action accepted for withdrawn, contested, or missing evidence; or any denominator omitted.
- Population: `synthetic_scripted`. No LLM, network service, or external tool is called.
- Costs: report local elapsed time and operation counts; model calls/tokens/USD are zero. Runtime is descriptive and host-dependent.

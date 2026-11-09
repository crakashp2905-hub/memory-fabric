# Benchmark agent adapter

`benchmarks.agent_adapter.AgentAdapter` is the transport-neutral decision boundary for scripted and future external-model benchmark arms. Each implementation receives a `TaskEnvelope` and returns an `AgentResponse`; it does not receive hidden oracle labels or direct access to the benchmark scheduler. `ScriptedPolicyAdapter` is the deterministic offline implementation.

The adapter protocol has no model SDK, HTTP client, or network dependency. Interface tests block socket connection creation and verify action/abstain behavior. Future model adapters can implement `decide` while leaving the task manifest, evidence gateway, scoring, and result schema unchanged. Model-backed results must use a distinct `real_model_agent` population label.

# How to use Memory Fabric

Memory Fabric gives agents a governed, correctable memory store. An agent
stores a fact with its source, retrieves only memories it is currently allowed
to use, cites the memories it relies on, and checks authority again before a
protected action. Corrections are previewed before they are applied, and the
event log records the correction and any retractions owed to other stores.

## Start with a local store

Follow [Quickstart](QUICKSTART.md) to install the package, choose a `personal`,
`team`, or `regulated` mode, and run the complete store/retrieve/correct demo.
Use `memory-fabric --db <your-store> doctor` if you need a health check.

## Connect your agent and choose its model

Use [Any agent, any model](guides/any-agent-any-model.md) to connect an MCP or
Python agent, select a provider/model, pull a local Ollama model, or import a
declarative agent manifest. Each agent should have its own ID. The host decides
which tools an uploaded manifest can use; an upload cannot grant itself tools.

## The everyday memory loop

1. **Remember** information with a clear source and scope. Use `derive` when a
   conclusion depends on earlier memories so the relationship stays visible.
2. **Retrieve** for the current task. Inspect the exposed results and their
   authority; retrieval is governed and logged.
3. **Cite** the memories that actually informed the answer or action. A
   retrieval alone does not prove that the agent used the memory.
4. **Check before acting.** For protected actions, use the action fence and
   revalidate the evidence at the point of use.
5. **Correct carefully.** Preview the correction, review downstream effects,
   then apply it. Verify that stale memories are no longer exposed and that
   correction notices reached relevant copies.

## Learn from the history

Use the dashboard to inspect memory lineage, exposure, citations, authority,
and correction impact. Those signals answer different questions: being
retrieved does not mean a memory was cited; a citation does not grant current
permission; and an influence edge does not prove that the memory changed a
decision.

Counterfactual Decision Memory (CDM) is a separate experimental feature for
bounded archival capture and deterministic, simulation-only replay. Begin with
[the CDM API and limitations](CAUSAL_REPLAY_API.md). The replay certificate
does not authorize actions, and synthetic examples do not establish real-world
causality or improved agent accuracy.

## Where to go next

- [Integrations](INTEGRATIONS.md) for MCP, HTTP, SDKs, and framework adapters.
- [Data access paths](DATA_ACCESS.md) for the enforcement applied by each API.
- [Limitations](LIMITATIONS.md) before relying on behavior outside measured
  cases.
- [Troubleshooting](TROUBLESHOOTING.md) when a command or request is refused.

# Any agent, any model

Memory Fabric does not care which agent or which model you use. Each agent
connects with its own id, and every model-backed feature uses the model you
name.

## 1. Connect your agent tool

```bash
memory-fabric connect --list
memory-fabric --db memory/store.db connect cursor --agent cursor-alice --write
```

| tool | how |
|---|---|
| Claude Code | `connect claude-code` prints the `claude mcp add` line |
| Claude Desktop, Cursor, Windsurf, Gemini CLI, Zed, Cline | `connect <tool> --write` merges into its MCP config |
| VS Code (Copilot agent mode), Continue | `connect <tool> --write` writes the workspace file |
| OpenAI Codex CLI | `connect codex --write` appends to `~/.codex/config.toml` |
| any language | `connect http`: the agent HTTP API with a credential per agent |
| Python frameworks | `connect python`: function tools for LangGraph, OpenAI Agents, CrewAI, AutoGen |

`--write` keeps the previous file as `.bak` and touches nothing but the
`memory-fabric` entry. Give each tool, or each person's copy of a tool, its own
`--agent` id: that is how the dashboard tells their memories apart.

Several agents, one store: point them all at the same `--db`. For more than a
few processes, run one `agent-api` and connect the agents over HTTP.

## 2. Choose your model

```bash
memory-fabric models                                     # what is ready on this machine
export MEMORY_FABRIC_MODEL=anthropic:claude-opus-5-5     # or any provider below
memory-fabric models --test "$MEMORY_FABRIC_MODEL"
```

Users can also persist a personal selection without changing shell startup
files. `MEMORY_FABRIC_MODEL` still takes precedence for deployments:

```bash
memory-fabric models --select ollama:qwen2.5:7b
memory-fabric models --pull ollama:qwen2.5:7b
```

`--pull` is intentionally local-Ollama-only. Hosted models are selected by
name and remain at their provider; API keys continue to come only from the
environment.

| provider | example | needs |
|---|---|---|
| Anthropic | `anthropic:claude-opus-5-5` | `ANTHROPIC_API_KEY`, `pip install ".[claude]"` |
| OpenAI | `openai:gpt-4.1-mini` | `OPENAI_API_KEY` |
| Azure OpenAI | `azure:<deployment>` | `MF_AZURE_ENDPOINT`, `AZURE_OPENAI_API_KEY` |
| Google Gemini | `gemini:gemini-2.5-flash` | `GEMINI_API_KEY` |
| OpenRouter, Groq, Together, Mistral, DeepSeek, Fireworks | `groq:llama-3.3-70b-versatile` | the provider's key |
| Ollama, LM Studio | `ollama:qwen2.5:7b` | a local server, no key |
| vLLM | `vllm:<model>` | `MF_VLLM_URL` |
| anything OpenAI-compatible | `compat:<model>@https://host/v1` | `MF_COMPAT_API_KEY` if it wants one |
| Claude Code's login | `claude-cli:sonnet` | the `claude` command |

Keys are read from the environment for each call and never stored. Every call
is logged with the model, a hash of the prompt (never the prompt), token
counts and cost; cost is filled in only from prices you supply, never guessed.

```python
from memory_fabric.models import ModelClient

llm = ModelClient("ollama:qwen2.5:7b", prices={"qwen2.5:7b": (0, 0)})
print(llm.complete("Summarise: ...").text, llm.log.totals())
```

## Upload a portable agent definition

Agent uploads are declarative JSON, not executable packages. This keeps an
uploaded agent inspectable and prevents an upload from running code merely by
being added to the catalog.

```json
{
  "schema": "memory-fabric-agent-v1",
  "id": "researcher",
  "name": "Researcher",
  "description": "Finds and synthesises evidence",
  "model": "ollama:qwen2.5:7b",
  "system_prompt": "Cite the evidence used for each conclusion.",
  "tools": ["recall", "remember"]
}
```

```bash
memory-fabric agents --import researcher.json
memory-fabric agents
memory-fabric --json agents
```

Imports reject unknown fields, malformed model specs, oversized prompts and
duplicate ids unless `--replace` is explicit. The catalog contains model names
and agent instructions, but never provider credentials. A host application
chooses how to instantiate the manifest and remains responsible for granting
its tools; an uploaded agent cannot grant itself capabilities.

## 4. Choose your embedding model

```bash
export MEMORY_FABRIC_EMBEDDER=openai:text-embedding-3-small   # or ollama:nomic-embed-text,
                                                              # fastembed:BAAI/bge-small-en-v1.5
```

`serve`, `mcp` and `agent-api` use it when it is set. In Python:
`MemoryFabric("store.db", **retrievers.from_environment())`. Details and
measurements: [RETRIEVAL.md](../RETRIEVAL.md).

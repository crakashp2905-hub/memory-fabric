# Historical surface authorization inventory

This inventory defines the trust boundary for every supported historical read
surface. “Historical” never changes who is authorized **now**.

| Surface | Carries memory content? | Authorization rule | Executable evidence |
|---|---:|---|---|
| `history_query.query` | Yes | Historical tenant/scope eligibility intersected with current visibility, lifecycle, erasure, and `use` decision | `tests/test_history_query.py` |
| `retrieve(as_of=..., until=...)` and `reconstruct(...)` | Yes / authorized terms | Normal current retrieval gates run before temporal filtering or graph traversal | `tests/test_bitemporal.py`, `tests/test_data_access_paths.py` |
| Agent SDK, agent API, MCP adapter | No raw history method | Only enforced reads are exposed; raw `history`, `get`, state, and audit inspection are absent | `tests/test_data_access_paths.py`, `tests/test_mcp.py` |
| Audit export | No | Deliberately content-free; memory payloads are reduced to identifiers and governance metadata | `tests/test_posture.py` |
| Branch history/diff/snapshot | No stored memory content | IDs, digests, operations, and current admissibility only; branch content is read through `view`, which calls current `use` authorization | `tests/test_branching.py` |
| Operator dashboard/detail | Yes | Administrative inspection surface behind observability authentication/roles; secret values are additionally scrubbed and erasure replaces all historical plaintext | `tests/test_observability.py`, `tests/test_erasure_residue.py` |
| `MemoryFabric.history`, projection state, incident replay | Yes | In-process operator/forensic APIs, explicitly excluded from agent and tenant clients | `tests/test_data_access_paths.py` |

Collection-grant revocation is tested both before and after the historical
snapshot. Withdrawal and erasure override an older readable snapshot. Because
credentials are revalidated on every service call and agent-facing clients do
not expose forensic methods, a revoked credential cannot reach raw history.
Exports that may leave the process contain no memory content, including prior
versions and erased values.

The raw in-process object remains an operator capability. Code holding a
`MemoryFabric` instance is inside the database trust boundary and must not be
handed to an untrusted agent; use the SDK, service session, or adapter instead.


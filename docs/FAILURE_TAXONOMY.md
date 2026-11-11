# Multi-agent failure attribution

The matched-arm report includes a trace for every wrong decision. `failure_taxonomy.categories` lists the frozen classes; each trace binds a seed-specific task ID, arm, family, evidence ID (or `NO_EVIDENCE`), observed guard reason, affected-agent count, and all applicable classes. Agent-decision denominators are retained per arm and family. If a task has no wrong decisions it has no failure trace; it remains in the attempted denominator.

The classes cover retrieval misses, acting without sufficient evidence, false policy refusals, agent disagreement, and tool/API exceptions. This run measures authorization decisions only, so coordination and tool-error counts can be zero; that is reported as an unobserved event count, not as a guarantee about those systems.

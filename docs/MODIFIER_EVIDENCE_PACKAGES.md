# Answer-modifying evidence packages

A fact can change an answer without restating the question or serving as a
derivation premise. Memory Fabric represents that relation explicitly:

```text
modifier --QUALIFIES--> selected answer/rule
```

When `follow_relations=True`, retrieval and chain reconstruction pull every
currently eligible qualifier immediately after the memory it qualifies. In an
`EvidenceChain`, the modifier is marked `DEPENDENCY_REQUIRED`, has no query
term coverage, and is `necessary=True` because the declared relation says its
absence changes the answer.

`tests/test_modifier_packages.py` builds five seeded multi-hop fixtures. Each
contains a source, a derived baseline rule, a derived answer, and a site margin
whose wording shares no query tokens. Without relation following, the package
computes the base figure. With it, the modifier remains in the package and the
computed figure changes by the declared margin.

Relations do not bypass governance. A qualifier must pass the same current
tenant, scope, lifecycle, erasure, and hostile-source eligibility gates as
every other memory. Relation discovery remains explicit or extraction-driven;
the system does not fabricate a modifier link from similarity alone.


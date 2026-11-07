# Opt-in deterministic query routing

Query-family routing is enabled only by `retrieve(..., profile="adaptive")` or
an explicit `method="auto"`; the default store method is unchanged.

The deterministic route table is:

| Recognized shape | Trained embedder | Hashing/no trained embedder |
|---|---|---|
| identifier or measured value | lexical | lexical |
| temporal wording | lexical | lexical |
| causal/multi-hop wording | hybrid | lexical |
| recognized semantic wording | hybrid | lexical |
| unrecognized, empty, or opaque | lexical | lexical |

Routing happens inside `_search` only after tenant, scope, lifecycle,
hostile-source, validity, collection, and contested-state eligibility has been
computed. Every ranking arm receives the same `eligible` ID set, so choosing a
route cannot make a forbidden memory rankable. The adaptive profile does not
enable contested content or change authorization policy.

The fallback is deliberately lexical: hashing vector and hybrid arms lose to
lexical on the measured full-history LongMemEval run, and an unknown query
shape is not evidence that semantic fusion is appropriate.


# Known gaps

What the masterplan asks for that this repository does not yet do, in one place. Each line links to
the tracker row that says why. Product limitations for users are in [LIMITATIONS.md](LIMITATIONS.md).

## Engineering

- **Format adapters have bounded fidelity.** CSV preserves cells and physical source spans; HTML extracts text without browser/CSS layout; DOCX covers body paragraphs and table rows; optional PDF extracts page text and refuses textless pages. OCR, PDF tables, DOCX headers/footers and visual layout verification remain open (MF-007).
- **Historical reads are bounded explicit-ID queries.** Experimental `history_query.query` intersects current and historical authorization; historical semantic search, checkpoint acceleration and the `retrieve(known_at=τ)` overload remain open (MF-017).
- **Typed queries cover writer-typed fields only.** No extraction of entities or relations; the exhaustive-filter study failed (MF-010, MF-039).
  Join/aggregate completeness now includes missing or malformed scalar keys rather than silently dropping them. These experimental queries do not establish real-world truth.
- **The default compaction summariser does not compress** a log whose lines all carry values; it keeps every value by design (MF-038).
- **Encrypted stores move only with backup/restore** (SQLite) or the database's tools: `export-events` keeps every tombstone, but encrypted content is sealed to its store and `import-events` refuses it (GOV-16).
- **A reused idempotency key is checked against the action only when the first call described it.** Both action gates record what a key commits to (tool, actor, target, parameters, receipt context, tenant and source versions) on the attempt and outcome events and refuse a different action under a used key with `idempotency_key_payload_mismatch` (`tests/test_action_fence_typed.py::IdempotencyBinding`). In the typed gate (`actions_typed`), a first call made with neither a `request` nor a `receipt_context` records no binding, so a later call under that key cannot be compared and is still reported as already executed. The episode runtime always passes a request (agent-validation checklist W08-02).

## Evidence

- **Only one public benchmark has been run with a model, and only a small local one** (PersonaMem, qwen2.5:3b, descriptive). Harvey LAB, τ-knowledge, WideSearch, SWE-bench, AA-LCR and the rest are NOT_RUN or BLOCKED with reasons in the [scoreboard](../research/results/BENCHMARK_SCOREBOARD.md).
- **33 of 100 recorded results do not name the commit** that produced them; none records a dataset digest or prompt hash ([manifest](../research/results/MANIFEST.json)).
- **Multi-host behaviour is measured on one physical host** (GOV-20, MF-021, MF-046).

## Outside the repository

External security review, independent replication, onboarding study with outside developers,
design partners, pricing and licence strategy (MF-022–MF-029, MF-050).

See [MASTERPLAN_TRACKER.md](MASTERPLAN_TRACKER.md) for every item.

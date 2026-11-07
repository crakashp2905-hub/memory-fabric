# Retrieval package status API

`RetrievalResult.assessment(question)` reports three different questions with
three non-interchangeable types:

- `RetrievalRanking.top_score`: how strongly the retriever ranked the nearest
  exposed item. It is not a truth, validity, or authorization score.
- `EvidenceValidity`: whether the package is empty, entirely active evidence,
  or contains evidence still contested or otherwise unvalidated.
- `DecisionReadiness`: whether the package supports an answer, requires
  abstention, or requires review because validity or conflict is unresolved.

The existing `RetrievalResult.answerability()` method remains available. The
new assessment composes it without deriving validity from ranking. In
particular, a highly ranked contested memory is `INVALID` and `REVIEW`, while
valid near-neighbours that do not cover the question are `ABSTAIN`.

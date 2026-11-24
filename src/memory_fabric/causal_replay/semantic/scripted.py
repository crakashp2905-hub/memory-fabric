"""A deterministic stand-in advisor for contract tests and scripted arms. Not a model.

It answers the same typed questions with fixed lexical rules, and every receipt
says ``evidence_level: SCRIPTED`` so no result produced with it can be read as
model inference (VEGA-CDM-131). ``answers`` lets a test script exact replies,
including malformed ones.
"""

from __future__ import annotations

__stability__ = "experimental"

import hashlib
from dataclasses import dataclass, field
from typing import Any, Mapping

from .advice import Advice, Answer, Question, parse_answer


@dataclass
class ScriptedAdvisor:
    answers: Mapping[str, Any] = field(default_factory=dict)
    calls: int = 0

    def decide(self, state: str, questions: Mapping[str, Question]) -> Advice:
        self.calls += 1
        out: dict[str, Answer] = {}
        for name, q in questions.items():
            raw = self.answers.get(name)
            if callable(raw):
                raw = raw(state, q)
            out[name] = parse_answer(q, raw if raw is not None else self._rule(state, q))
        digest = hashlib.sha256(state.encode()).hexdigest()
        return Advice(out, {"adapter": "scripted", "evidence_level": "SCRIPTED",
                            "receipt_digest": digest, "status": "ANSWERED"})

    @staticmethod
    def _rule(state: str, q: Question) -> dict[str, Any]:
        text = state.lower()
        if q.kind == "boolean":
            p = 0.8 if any(w in text for w in ("bias", "drift", "disagree", "differs")) else 0.2
            return {"boolean": p, "probs": {"true": p, "false": 1 - p},
                    "prediction_set": ["true" if p > 0.5 else "false"], "abstain": False, "unbound": False}
        if q.kind == "score":
            n = len(q.criteria)
            probs = {str(i): 1 / n for i in range(n)}
            return {"score": 0, "probs": probs, "prediction_set": [str(i) for i in range(n)],
                    "abstain": True, "unbound": False}
        labels = q.labels
        pick = labels[0]
        for label in labels:
            if label in text:
                pick = label
        probs = {label: (0.7 if label == pick else 0.3 / (len(labels) - 1)) for label in labels}
        return {"choice": pick, "probs": probs, "prediction_set": [pick], "abstain": False,
                "unbound": False}

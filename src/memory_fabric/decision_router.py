"""Dependency-free, deterministic System 1/System 2 routing from local features."""
from __future__ import annotations

__stability__ = "experimental"

from dataclasses import dataclass

SYSTEM1 = "system1"
SYSTEM2 = "system2"
ABSTAIN = "abstain"

_RISKS = frozenset({"low", "medium", "high", "critical"})
_CONSEQUENTIAL_TOOLS = frozenset({"write", "execute", "external", "destructive"})
_KNOWN_TOOLS = frozenset({"read", "analysis", *_CONSEQUENTIAL_TOOLS})


@dataclass(frozen=True)
class RoutingFeatures:
    """Locally available facts; no probability model or network call is consulted."""

    risk: str
    evidence_gaps: int
    tool_class: str
    system2_budget_tokens: int
    estimated_system2_tokens: int

    def __post_init__(self) -> None:
        if not isinstance(self.risk, str) or self.risk not in _RISKS:
            raise ValueError(f"risk must be one of {sorted(_RISKS)}")
        if (isinstance(self.evidence_gaps, bool) or not isinstance(self.evidence_gaps, int)
                or self.evidence_gaps < 0):
            raise ValueError("evidence_gaps must be a non-negative integer")
        if not isinstance(self.tool_class, str) or not self.tool_class.strip():
            raise ValueError("tool_class must be a non-empty string")
        for name, value in (("system2_budget_tokens", self.system2_budget_tokens),
                            ("estimated_system2_tokens", self.estimated_system2_tokens)):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")


@dataclass(frozen=True)
class RoutingDecision:
    route: str
    reasons: tuple[str, ...]
    estimated_system2_tokens: int
    available_system2_tokens: int


def route_system(features: RoutingFeatures) -> RoutingDecision:
    """Route deterministic local risk/evidence/tool features under a token budget.

    Consequential classes and unknown future classes are kept out of System 1.
    If escalation is required but cannot fit the declared budget, abstain; never
    silently downgrade the request to the faster path.
    """
    reasons: list[str] = []
    if features.risk in {"high", "critical"}:
        reasons.append("elevated_risk")
    if features.evidence_gaps:
        reasons.append("evidence_gaps")
    if features.tool_class in _CONSEQUENTIAL_TOOLS:
        reasons.append("consequential_tool")
    elif features.tool_class not in _KNOWN_TOOLS:
        reasons.append("unrecognized_tool_class")
    if not reasons:
        return RoutingDecision(SYSTEM1, ("low_risk_complete_evidence_read_or_analysis",),
                               features.estimated_system2_tokens,
                               features.system2_budget_tokens)
    if features.system2_budget_tokens < features.estimated_system2_tokens:
        return RoutingDecision(ABSTAIN, tuple((*reasons, "system2_budget_insufficient")),
                               features.estimated_system2_tokens,
                               features.system2_budget_tokens)
    return RoutingDecision(SYSTEM2, tuple(reasons), features.estimated_system2_tokens,
                           features.system2_budget_tokens)

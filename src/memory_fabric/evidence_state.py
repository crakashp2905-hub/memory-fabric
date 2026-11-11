"""Evidence-state lattice, separate from action authorization.

The ordering below is an information order: higher values carry at least as
much state information. It is not a trust score. In particular, ``withdrawn``
and ``stale`` are flags that coexist with support information, while callers
still apply their own risk and authorization policy before acting.
"""
from __future__ import annotations

__stability__ = "beta"

from dataclasses import dataclass
from enum import IntEnum


class SupportLevel(IntEnum):
    UNKNOWN = 0
    SUPPORTED = 1
    INDEPENDENTLY_CORROBORATED = 2


@dataclass(frozen=True, slots=True)
class EvidenceState:
    """A product-lattice element describing support and adverse evidence flags."""

    support: SupportLevel = SupportLevel.UNKNOWN
    disputed: bool = False
    withdrawn: bool = False
    stale: bool = False

    def __le__(self, other: object) -> bool:
        if not isinstance(other, EvidenceState):
            return NotImplemented
        return (self.support <= other.support and
                self.disputed <= other.disputed and
                self.withdrawn <= other.withdrawn and self.stale <= other.stale)

    def join(self, other: EvidenceState) -> EvidenceState:
        """Least upper bound: combine information from two observations."""
        return EvidenceState(max(self.support, other.support), self.disputed or other.disputed,
                             self.withdrawn or other.withdrawn, self.stale or other.stale)

    def meet(self, other: EvidenceState) -> EvidenceState:
        """Greatest lower bound: retain only information common to both."""
        return EvidenceState(min(self.support, other.support), self.disputed and other.disputed,
                             self.withdrawn and other.withdrawn, self.stale and other.stale)


UNKNOWN = EvidenceState()
DISPUTED = EvidenceState(disputed=True)
WITHDRAWN = EvidenceState(withdrawn=True)
STALE = EvidenceState(SupportLevel.SUPPORTED, stale=True)
SUPPORTED = EvidenceState(SupportLevel.SUPPORTED)
INDEPENDENTLY_CORROBORATED = EvidenceState(SupportLevel.INDEPENDENTLY_CORROBORATED)


def named_states() -> dict[str, EvidenceState]:
    """The six canonical states named by the offline qualification contract."""
    return {
        "unknown": UNKNOWN,
        "disputed": DISPUTED,
        "withdrawn": WITHDRAWN,
        "stale": STALE,
        "supported": SUPPORTED,
        "independently_corroborated": INDEPENDENTLY_CORROBORATED,
    }

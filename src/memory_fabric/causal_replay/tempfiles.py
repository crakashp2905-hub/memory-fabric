"""Private temporary workspaces confined to the checkout's CDM result area."""

from __future__ import annotations

__stability__ = "experimental"

from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterator

from .types import CDMError


def allowed_root() -> Path:
    """The only parent allowed for ephemeral CDM artifacts in this checkout."""
    return Path(__file__).resolve().parents[3] / "research" / "results" / "cdm"


def validate_parent(parent: str | Path | None = None) -> Path:
    root = allowed_root().resolve()
    candidate = root if parent is None else Path(parent).resolve()
    if candidate != root and root not in candidate.parents:
        raise CDMError("temporary workspace parent is outside the approved CDM result root")
    candidate.mkdir(parents=True, exist_ok=True)
    if not candidate.is_dir():
        raise CDMError("temporary workspace parent must be a directory")
    return candidate


@contextmanager
def temporary_workspace(parent: str | Path | None = None) -> Iterator[Path]:
    """Create and always remove an isolated directory under the approved root."""
    approved_parent = validate_parent(parent)
    root = allowed_root().resolve()
    with TemporaryDirectory(prefix="cdm-work-", dir=approved_parent) as raw_path:
        workspace = Path(raw_path).resolve()
        if workspace == root or root not in workspace.parents:
            raise CDMError("resolved temporary workspace escaped the approved root")
        yield workspace

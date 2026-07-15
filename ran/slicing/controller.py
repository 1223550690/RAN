from __future__ import annotations

from ran.contracts import SlicePolicy
from .policy import default_slice_policies


def update_slice_policies() -> list[SlicePolicy]:
    """Project implementation detail."""

    return default_slice_policies()

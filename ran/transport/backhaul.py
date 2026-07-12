from __future__ import annotations

from ran.contracts import N3ForwardingResult


def apply_backhaul(result: N3ForwardingResult, *, capacity_mbps: float = 1000.0) -> N3ForwardingResult:
    """Project implementation detail."""

    _ = capacity_mbps
    return result

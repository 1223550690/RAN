from __future__ import annotations

from ran.contracts import MacAllocation


def summarize_slice_usage(allocations: list[MacAllocation]) -> dict[str, int]:
    """Project implementation detail."""

    usage: dict[str, int] = {}
    for allocation in allocations:
        usage[allocation.slice_id] = usage.get(allocation.slice_id, 0) + allocation.prbs
    return usage

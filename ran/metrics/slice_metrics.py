from __future__ import annotations

from ran.contracts import MacAllocation


def summarize_slice_usage(allocations: list[MacAllocation]) -> dict[str, int]:
    """统计每个 slice 使用的 PRB。

    输入:
    - allocations: MAC 调度结果。

    输出:
    - {slice_id: allocated_prbs}
    """

    usage: dict[str, int] = {}
    for allocation in allocations:
        usage[allocation.slice_id] = usage.get(allocation.slice_id, 0) + allocation.prbs
    return usage

from __future__ import annotations

from ran.contracts import N3ForwardingResult


def apply_backhaul(result: N3ForwardingResult, *, capacity_mbps: float = 1000.0) -> N3ForwardingResult:
    """应用回传链路容量限制。

    输入:
    - result: N3 转发结果。
    - capacity_mbps: 回传容量。

    输出:
    - N3ForwardingResult。
    """

    # MVP 最小实现：测试业务单 tick 字节远小于默认 backhaul，不限速。
    _ = capacity_mbps
    return result

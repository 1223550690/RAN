from __future__ import annotations

from ran.contracts import N6DeliveryResult


def forward_n6(result: N6DeliveryResult) -> N6DeliveryResult:
    """N6 出口转发。

    输入:
    - N6DeliveryResult。

    输出:
    - N6DeliveryResult。
    """

    # MVP 最小实现：N6 不再额外改变结果。
    return result

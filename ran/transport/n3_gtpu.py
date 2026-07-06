from __future__ import annotations

from ran.contracts import N3ForwardingResult


def build_n3_result(result: N3ForwardingResult) -> N3ForwardingResult:
    """N3/GTP-U 输出边界。

    输入:
    - gNB-CU-UP 生成的 N3ForwardingResult。

    输出:
    - N3ForwardingResult。
    """

    # MVP 最小实现：函数只作为模块边界保留。
    return result

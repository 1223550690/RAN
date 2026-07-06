from __future__ import annotations

from ran.contracts import TransmissionResult


def receive_radio(result: TransmissionResult) -> TransmissionResult:
    """gNB-RU 接收无线传输。

    输入:
    - TransmissionResult。

    输出:
    - TransmissionResult: MVP 中直接传给 DU/CU-UP。
    """

    # MVP 最小实现：RU 不单独处理 RF 前端，只作为架构边界保留。
    return result

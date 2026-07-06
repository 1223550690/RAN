from __future__ import annotations

from ran.contracts import N6DeliveryResult


def deliver_to_data_network(result: N6DeliveryResult) -> N6DeliveryResult:
    """Data Network 接收入口。

    输入:
    - N6DeliveryResult: UPF 经 N6 送出的业务结果。

    输出:
    - N6DeliveryResult: MVP 中直接返回原对象，表示 youtube_server 已接收。
    """

    # MVP 最小实现：不模拟互联网路由和服务器处理，只确认 N6 delivered_bytes。
    return result

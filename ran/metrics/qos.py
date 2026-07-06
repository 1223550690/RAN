from __future__ import annotations

from ran.contracts import N3ForwardingResult, N6DeliveryResult, QosMetrics, TransmissionResult


def calculate_qos(
    *,
    requested_bytes: int,
    transmission: TransmissionResult,
    n3: N3ForwardingResult,
    n6: N6DeliveryResult,
    delay_budget_ms: float,
) -> QosMetrics:
    """计算端到端 QoS。

    输入:
    - requested_bytes: 请求字节数。
    - transmission/n3/n6: 各段结果。
    - delay_budget_ms: QoS 时延预算。

    输出:
    - QosMetrics。
    """

    total_duration = transmission.transmission_delay_ms + n3.n3_delay_ms + n6.n6_delay_ms
    # MVP 最小实现：latency_ms 表示单批无线传输路径时延，不表示整个大文件上传完成时间。
    packet_path_delay = 1.0 + n3.n3_delay_ms + n6.n6_delay_ms
    # 真实丢包率只统计已经确认不可恢复的丢弃字节。
    # 排队中或等待 HARQ/RLC 重传的数据不属于 loss。
    lost = transmission.dropped_bytes + n3.n3_loss_bytes + n6.n6_loss_bytes
    loss_rate = lost / requested_bytes if requested_bytes else 0.0
    throughput = (n6.delivered_bytes * 8) / max(total_duration, 1.0) / 1000.0
    congestion = transmission.prbs >= 100 and n6.delivered_bytes < requested_bytes
    return QosMetrics(
        throughput_mbps=throughput,
        latency_ms=packet_path_delay,
        packet_loss_rate=loss_rate,
        congestion=congestion,
        service_satisfied=packet_path_delay <= delay_budget_ms and loss_rate < 0.1,
    )

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
    """Project implementation detail."""

    total_duration = transmission.transmission_delay_ms + n3.n3_delay_ms + n6.n6_delay_ms
    packet_path_delay = 1.0 + n3.n3_delay_ms + n6.n6_delay_ms
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

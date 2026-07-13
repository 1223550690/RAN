from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class QosMetrics:
    """Project implementation detail."""

    throughput_mbps: float
    latency_ms: float
    packet_loss_rate: float
    congestion: bool
    service_satisfied: bool


@dataclass(slots=True)
class EndToEndResult:
    """Project implementation detail."""

    service_id: str
    ue_id: str
    target: str
    slice_id: str
    access_type: str  # access_type: 3gpp/non_3gpp。
    requested_bytes: int
    delivered_bytes: int
    failed_bytes: int
    qos: QosMetrics

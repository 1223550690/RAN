from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class QosMetrics:
    """QoS 指标。

    输入字段:
    - PHY、N3、N6 的交付、失败、时延数据。

    输出字段:
    - throughput/latency/loss/congestion/service_satisfied。
    """

    throughput_mbps: float  # throughput_mbps: 当前 tick 的实时吞吐，非累计平均吞吐。
    latency_ms: float  # latency_ms: 端到端估计时延。
    packet_loss_rate: float  # packet_loss_rate: 真实丢包率，只统计 dropped/N3/N6 等不可恢复丢弃，不包含队列剩余或重传。
    congestion: bool  # congestion: 是否拥塞。
    service_satisfied: bool  # service_satisfied: 是否满足基本 QoS。


@dataclass(slots=True)
class EndToEndResult:
    """端到端业务结果。

    输出字段:
    - 汇总从 AgentIntent 到 DataNetwork 的主要结果，便于测试和日志展示。
    """

    service_id: str  # service_id: 业务 ID。
    ue_id: str  # ue_id: UE 标识。
    target: str  # target: 目标服务。
    slice_id: str  # slice_id: 切片标识。
    access_type: str  # access_type: 3gpp/non_3gpp。
    requested_bytes: int  # requested_bytes: 请求总字节。
    delivered_bytes: int  # delivered_bytes: 最终送达字节。
    failed_bytes: int  # failed_bytes: 当前未送达字节；MVP 中更接近 undelivered/remaining，不等同于真实丢包。
    qos: QosMetrics  # qos: QoS 汇总指标。

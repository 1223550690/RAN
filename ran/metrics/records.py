from __future__ import annotations

from ran.contracts import EndToEndResult, QosMetrics


def build_end_to_end_result(
    *,
    service_id: str,
    ue_id: str,
    target: str,
    slice_id: str,
    access_type: str,
    requested_bytes: int,
    delivered_bytes: int,
    qos: QosMetrics,
) -> EndToEndResult:
    """构造端到端结果记录。

    输入:
    - 业务、接入、交付和 QoS 字段。

    输出:
    - EndToEndResult。
    """

    return EndToEndResult(
        service_id=service_id,
        ue_id=ue_id,
        target=target,
        slice_id=slice_id,
        access_type=access_type,
        requested_bytes=requested_bytes,
        delivered_bytes=delivered_bytes,
        failed_bytes=max(0, requested_bytes - delivered_bytes),
        qos=qos,
    )

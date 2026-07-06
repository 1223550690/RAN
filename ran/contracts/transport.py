from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class N3ForwardingResult:
    """N3/GTP-U 转发结果。

    输入字段:
    - TransmissionResult.successful_bytes。

    输出字段:
    - forwarded_bytes/n3_delay_ms/n3_loss_bytes 供 UPF 和 QoS 使用。
    """

    tunnel_id: str  # tunnel_id: N3 隧道标识。
    teid: int  # teid: GTP-U TEID。
    ue_id: str  # ue_id: UE 标识。
    pdu_session_id: int  # pdu_session_id: PDU Session。
    upf_id: str  # upf_id: 目标 UPF。
    forwarded_bytes: int  # forwarded_bytes: N3 成功转发字节。
    n3_delay_ms: float  # n3_delay_ms: N3 固定/拥塞时延。
    n3_loss_bytes: int  # n3_loss_bytes: N3 丢弃字节。


@dataclass(slots=True)
class N6DeliveryResult:
    """N6/Data Network 交付结果。

    输入字段:
    - UPF 解封装后的用户面字节。

    输出字段:
    - delivered_bytes/end_to_end_delay_ms 供最终结果使用。
    """

    dnn: str  # dnn: Data Network Name。
    target: str  # target: 目标服务。
    delivered_bytes: int  # delivered_bytes: Data Network 收到字节。
    n6_delay_ms: float  # n6_delay_ms: N6 时延。
    n6_loss_bytes: int  # n6_loss_bytes: N6 丢弃字节。

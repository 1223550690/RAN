from __future__ import annotations

from dataclasses import dataclass

from .common import Direction


@dataclass(slots=True)
class Drb:
    """Data Radio Bearer。

    输入字段:
    - QoSFlow/QFI 与 SDAP 映射规则。

    输出字段:
    - drb_id/qfi/slice_id/rlc_mode: PDCP、RLC、scheduler 使用。
    """

    drb_id: int  # drb_id: 数据无线承载 ID。
    ue_id: str  # ue_id: 所属 UE。
    pdu_session_id: int  # pdu_session_id: 所属 PDU Session。
    qfi: int  # qfi: 承载的 QoS Flow。
    slice_id: str  # slice_id: 关联切片。
    direction: Direction  # direction: UL 或 DL。
    rlc_mode: str  # rlc_mode: TM/UM/AM。
    priority: int  # priority: 调度优先级。


@dataclass(slots=True)
class RlcQueue:
    """RLC 队列快照。

    输入字段:
    - PDCP 输出批次和 DRB 配置。

    输出用途:
    - SchedulerRequest 的核心输入。Java 不接收完整 PDCP/RLC 对象，只接收此摘要。
    """

    ue_id: str  # ue_id: 所属 UE。
    drb_id: int  # drb_id: 队列所属 DRB。
    qfi: int  # qfi: QoS Flow 标识。
    slice_id: str  # slice_id: 网络切片标识。
    direction: Direction  # direction: UL 或 DL。
    rlc_mode: str  # rlc_mode: RLC 模式。
    queued_bytes: int  # queued_bytes: 等待首次发送的字节数。
    retransmission_bytes: int  # retransmission_bytes: 等待重传的字节数。
    head_of_line_delay_ms: float  # head_of_line_delay_ms: 队首等待时延。

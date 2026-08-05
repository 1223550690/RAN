from __future__ import annotations

from dataclasses import dataclass

from .common import Direction


@dataclass(slots=True)
class PduSession:
    """Project implementation detail."""

    pdu_session_id: int
    ue_id: str
    dnn: str
    slice_id: str
    pdu_session_type: str  # pdu_session_type: IPv4/IPv6/IPv4v6。
    ue_ip: str
    smf_id: str
    upf_id: str
    state: str = "ACTIVE"


@dataclass(slots=True)
class QoSFlow:
    """一个 UE PDU Session 内的 QoS Flow 摘要。"""

    ue_id: str  # ue_id: QFI 所属 UE，避免跨 UE 产生编号歧义。
    service_instance_id: str  # service_instance_id: 当前简化模型中的业务来源。
    pdu_session_id: int
    qfi: int  # qfi: QoS Flow Identifier。
    five_qi: int
    direction: Direction
    service_type: str
    priority: int
    packet_delay_budget_ms: float
    packet_error_rate: float
    resource_type: str
    slice_id: str
    gbr_mbps: float | None = None
    mbr_mbps: float | None = None


@dataclass(slots=True)
class SlicePolicy:
    """Project implementation detail."""

    slice_id: str
    priority: int
    min_prb_ratio: float
    max_prb_ratio: float
    delay_budget_ms: float

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from .common import Direction, Position


AccessType = Literal["3gpp", "non_3gpp"]
SelectedAccess = Literal["5g", "wifi", "auto"]


@dataclass(slots=True)
class UEState:
    """Project implementation detail."""

    ue_id: str
    agent_id: str
    position: Position
    rm_state: str = "DEREGISTERED"
    cm_state: str = "IDLE"
    rrc_state: str = "IDLE"
    ue_ip: str | None = None
    allowed_slices: list[str] = field(default_factory=list)


@dataclass(slots=True)
class UERequest:
    """由一个业务意图生成的 UE 网络请求。"""

    intent_id: str  # intent_id: 请求对应的意图标识。
    service_instance_id: str  # service_instance_id: 本次业务实例的全局标识。
    ue_id: str  # ue_id: 承载本次业务的 UE 标识。
    agent_id: str  # agent_id: UE 所属 Agent 标识。
    position: Position  # position: UE 当前地图坐标。
    direction: Direction  # direction: UL 或 DL。
    selected_access: SelectedAccess  # selected_access: 5g/wifi/auto。
    access_type: AccessType
    target: str
    dnn: str
    pdu_session_type: str  # pdu_session_type: IPv4/IPv6/IPv4v6。
    service_type: str
    requested_payload_bytes: int  # requested_payload_bytes: 应用层请求数据量。
    qos_hint: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class AccessSelection:
    """Project implementation detail."""

    selected_access: SelectedAccess
    access_type: AccessType
    access_node_id: str
    reason: str

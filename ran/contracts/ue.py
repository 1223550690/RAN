from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from .common import Direction, Position


AccessType = Literal["3gpp", "non_3gpp"]
SelectedAccess = Literal["5g", "wifi", "auto"]


@dataclass(slots=True)
class UEState:
    """Project implementation detail.

    输入字段:
    - ue_id/agent_id: UE 与 Agent 的绑定关系。
    - position: UE 当前地图坐标。

    输出字段:
    - rm_state/cm_state/rrc_state: 简化控制面状态。
    - ue_ip: PDU session 建立后分配的 UE IP。
    - cmax_transmit: Value indicating the configured maximum transmission power of the UE, to be used for the Power Headroom Report.
    """
    

    ue_id: str  # ue_id: UE/手机标识。
    agent_id: str  # agent_id: 绑定的 Agent 标识。
    position: Position  # position: UE 当前地图坐标。
    cmax_transmit: int#Default configured maximum transmission power in Decibels.
    ue_pusch: int #Default values for simulation
    rm_state: str = "DEREGISTERED"  # rm_state: 5GC 注册状态。
    cm_state: str = "IDLE"  # cm_state: 核心网连接管理状态。
    rrc_state: str = "IDLE"  # rrc_state: UE 与 gNB 的无线控制状态。
    
    ue_ip: str | None = None  # ue_ip: UE 在 PDU Session 中获得的 IP。
    allowed_slices: list[str] = field(default_factory=list)  # allowed_slices: 允许使用的切片。


@dataclass(slots=True)
class UERequest:
    """由一个业务意图生成的 UE 网络请求。"""

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
    intent_id: str = ""  # intent_id: 请求对应的意图标识(集成扩展,可选)。
    service_instance_id: str = ""  # service_instance_id: 本次业务实例的全局标识(集成扩展,可选)。

    @property
    def size_bytes(self) -> int:
        """兼容旧字段名 size_bytes(历史构造/读取仍在使用)。"""

        return self.requested_payload_bytes


@dataclass(slots=True)
class AccessSelection:
    """Project implementation detail."""

    selected_access: SelectedAccess
    access_type: AccessType
    access_node_id: str
    reason: str

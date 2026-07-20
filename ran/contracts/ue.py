from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from .common import Direction, Position


AccessType = Literal["3gpp", "non_3gpp"]
SelectedAccess = Literal["5g", "wifi", "auto"]


@dataclass(slots=True)
class UEState:
    """UE 运行状态。

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
    """UE 业务请求。

    输入字段:
    - ue_id/agent_id/position: 由 AgentIntent 和 UEState 得到。
    - selected_access/access_type: 预留 Wi-Fi non-3GPP 接入字段。
    - dnn/pdu_session_type/service_type/size_bytes/qos_hint: 5GC 与 QoS 映射输入。

    输出用途:
    - 进入 PDU session、IP traffic、QoS Flow 和切片分类流程。
    """

    ue_id: str  # ue_id: 发起业务的 UE。
    agent_id: str  # agent_id: 来源 Agent。
    position: Position  # position: UE 发起业务时的位置。
    direction: Direction  # direction: UL 或 DL。
    selected_access: SelectedAccess  # selected_access: 5g/wifi/auto。
    access_type: AccessType  # access_type: 3gpp 或 non_3gpp。
    target: str  # target: 应用目标服务。
    dnn: str  # dnn: Data Network Name，例如 internet。
    pdu_session_type: str  # pdu_session_type: IPv4/IPv6/IPv4v6。
    service_type: str  # service_type: video_upload/web/game 等。
    size_bytes: int  # size_bytes: 业务总字节数。
    qos_hint: dict[str, object] = field(default_factory=dict)  # qos_hint: 应用侧 QoS 偏好。


@dataclass(slots=True)
class AccessSelection:
    """接入选择结果。

    输入字段:
    - UERequest.selected_access/access_type。

    输出字段:
    - access_node_id: 当前服务节点。MVP 只使用 gNB；Wi-Fi 仅保留字段。
    - reason: 选择原因，方便调试与日志解释。
    """

    selected_access: SelectedAccess  # selected_access: 实际选中的接入。
    access_type: AccessType  # access_type: 3GPP 或 non-3GPP。
    access_node_id: str  # access_node_id: gNB 或未来 Wi-Fi AP 标识。
    reason: str  # reason: 接入选择说明。

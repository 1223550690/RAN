from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from .common import Position


AgentStatus = Literal["READY", "ACTIVE", "PAUSED", "COMPLETED", "FAILED"]


@dataclass(slots=True)
class AgentIntent:
    """Agent 提交给网络场景的单个业务意图。"""

    intent_id: str  # intent_id: 全局唯一意图标识。
    agent_id: str  # agent_id: 发起该意图的 Agent 标识。
    agent_pos: Position  # agent_pos: 创建意图时的 Agent 地图坐标。
    action: str  # action: upload/send_message 等日常动作。
    target: str  # target: 目标数据网络服务名称。
    content_type: str  # content_type: video/text/audio 等内容类型。
    service_type: str  # service_type: QoS 与切片分类使用的稳定业务类型。
    requested_payload_bytes: int  # requested_payload_bytes: 应用层请求传输的数据量。
    created_tick: int = 0  # created_tick: 意图创建的仿真 tick。
    duration_seconds: float | None = None  # duration_seconds: 连续业务(如 video_call)的持续时长;按数据量结束的业务为 None。
    qos_hint: dict | None = None  # qos_hint: QoS 参数提示;缺省时由 build_ue_request 使用默认值。
    direction: str = "UL"  # direction: 业务方向 UL/DL(集成扩展,默认上行,向后兼容)。


@dataclass(slots=True)
class AgentStateSnapshot:
    """AgentStateProvider 在指定 tick 返回的只读状态快照。"""

    agent_id: str  # agent_id: 场景建立时冻结的 Agent 标识。
    tick: int  # tick: 该状态所属的仿真 tick。
    position: Position  # position: Agent 当前地图坐标。
    status: AgentStatus  # status: Agent 当前运行状态。
    # 以下字段为 Agent 子系统扩展,带默认值以保持向后兼容。
    role: str = ""  # role: 角色,student/teacher/staff 等。
    activity_state: str = ""  # activity_state: 活动状态,如 planning/walking/network_active。
    current_intent_id: str | None = None  # current_intent_id: 当前活跃意图标识。
    destination_id: str | None = None  # destination_id: 当前目标语义引用。
    current_room_id: str | None = None  # current_room_id: 当前所在区域标识。
    waypoint_index: int = 0  # waypoint_index: 当前路径点序号。
    waypoint_count: int = 0  # waypoint_count: 当前路径点总数。
    waypoints: list[Position] = field(default_factory=list)  # waypoints: 当前规划路径点(地图渲染用,可选)。
    last_transition_tick: int = 0  # last_transition_tick: 最近一次状态迁移的 tick。
    error: str | None = None  # error: 最近一次错误信息,无错误时为 None。

from __future__ import annotations

from dataclasses import dataclass

from .common import Position


@dataclass(slots=True)
class AgentIntent:
    """Agent 行为意图。

    输入字段:
    - agent_id: 行为模拟中的 Agent 标识。
    - agent_pos: Agent 在地图中的当前位置。
    - action: Agent 想做的动作，例如 upload。
    - target: 应用层目标，例如 youtube_server。
    - content_type/size_bytes: 业务内容类型和大小。

    输出用途:
    - 由 UE request provider 转换为 UERequest。
    """

    agent_id: str  # agent_id: Agent 标识。
    agent_pos: Position  # agent_pos: Agent 当前地图坐标。
    action: str  # action: 行为动作，例如 upload。
    target: str  # target: 应用层目标服务。
    content_type: str  # content_type: 内容类型，例如 video。
    size_bytes: int  # size_bytes: 本次业务总字节数。

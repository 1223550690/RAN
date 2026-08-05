from __future__ import annotations

from typing import Protocol

from ran.contracts import AgentStateSnapshot, AgentStatus, Position

from .definitions import RanScenarioDefinition


class AgentStateProvider(Protocol):
    """向 RAN 编排层提供指定 tick 的 Agent 状态，不负责网络决策。"""

    def get_agent_states(self, *, tick: int) -> list[AgentStateSnapshot]:
        """返回场景中全部 Agent 的状态；不得动态增删 Agent。"""
        ...


class MockAgentStateProvider:
    """当前测试使用的静态 mock；后续可替换为真实 Agent 系统接口。"""

    def __init__(self, definition: RanScenarioDefinition) -> None:
        self._initial_positions = {
            item.agent_id: Position(item.intent.agent_pos.x, item.intent.agent_pos.y) for item in definition.agents
        }

    def get_agent_states(self, *, tick: int) -> list[AgentStateSnapshot]:
        """返回固定位置的 Agent 状态，Agent ID 集合在构造后保持不变。"""

        status: AgentStatus = "READY" if tick <= 0 else "ACTIVE"
        return [
            AgentStateSnapshot(
                agent_id=agent_id,
                tick=tick,
                position=Position(position.x, position.y),
                status=status,
            )
            for agent_id, position in self._initial_positions.items()
        ]

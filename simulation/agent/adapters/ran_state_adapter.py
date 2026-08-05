"""RAN 状态适配器:实现 ran.orchestration.AgentStateProvider 协议。

从 AgentRegistry 读取各 Agent 运行时状态,转换为 ran.contracts.AgentStateSnapshot。
无副作用:只读快照,不触发 LLM、移动或意图提交。
"""

from __future__ import annotations

from ran.contracts import AgentStateSnapshot, Position

from ..registry import AgentRegistry


class SimulationAgentStateProvider:
    """把 Agent 子系统状态桥接为 RAN 可读的 AgentStateSnapshot。"""

    def __init__(self, registry: AgentRegistry) -> None:
        self.registry = registry

    def get_agent_states(self, *, tick: int) -> list[AgentStateSnapshot]:
        snapshots: list[AgentStateSnapshot] = []
        for runtime in self.registry.runtimes():
            snapshot = runtime.to_snapshot(tick)
            snapshots.append(
                AgentStateSnapshot(
                    agent_id=snapshot.agent_id,
                    tick=tick,
                    position=Position(snapshot.position[0], snapshot.position[1]),
                    status=snapshot.lifecycle_status,  # type: ignore[arg-type]
                    role=snapshot.role,
                    activity_state=snapshot.activity_state,
                    current_intent_id=snapshot.current_intent_id,
                    destination_id=snapshot.destination_id,
                    current_room_id=snapshot.current_room_id,
                    waypoint_index=snapshot.waypoint_index,
                    waypoint_count=snapshot.waypoint_count,
                    waypoints=[Position(x, y) for x, y in snapshot.waypoints],
                    last_transition_tick=snapshot.last_transition_tick,
                    error=snapshot.error,
                )
            )
        return snapshots

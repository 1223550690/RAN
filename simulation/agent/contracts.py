"""Agent 子系统的数据契约。

职责边界:
- 只定义数据结构与枚举,不含任何执行逻辑。
- 本模块不依赖 ran 包;与 ran 的对接通过 adapters/ 完成。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

AgentRole = Literal["student", "teacher", "staff"]
"""角色枚举;扩展新角色时同步更新 configs/agents/roles.json。"""

AgentActivityState = Literal[
    "idle",
    "planning",
    "walking",
    "network_pending",
    "network_active",
    "blocked",
    "done",
]
"""活动状态:planning=正在请求/生成计划;walking=沿路径移动;network_pending=已到达、等待提交意图;
network_active=业务进行中(坐标冻结);blocked=计划或导航失败;done=无更多计划。"""

IntentType = Literal["video_call", "video_upload", "file_transfer", "message"]
"""意图类型枚举;业务量折算规则见 adapters/ran_intent_gateway.py。"""

LoopPolicy = Literal["stop", "repeat"]
"""模板计划耗尽后的行为:stop=结束;repeat=从头循环。"""


@dataclass(frozen=True, slots=True)
class AgentPlan:
    """LLM 或模板返回的语义计划:只决定"去哪里、做什么",不包含坐标。"""

    agent_id: str  # agent_id: 目标 Agent。
    destination_ref: str  # destination_ref: 语义目标引用(完整路径/名称/ID/别名)。
    intent_type: IntentType  # intent_type: 业务意图类型。
    intent_parameters: dict = field(default_factory=dict)  # intent_parameters: 业务参数,如 size_profile / duration_seconds。


@dataclass(frozen=True, slots=True)
class AgentSpawnDefinition:
    """单个 Agent 的冻结定义:身份、角色和出生点。"""

    agent_id: str  # agent_id: 场景建立后冻结的 Agent 标识。
    role: AgentRole  # role: 角色。
    spawn_position: tuple[float, float]  # spawn_position: 出生点全局坐标。
    ue_id: str | None = None  # ue_id: 默认 UE 标识;缺省时由 registry 生成。


@dataclass(frozen=True, slots=True)
class AgentPlanStep:
    """模板中单个 Agent 的一步计划。"""

    destination_ref: str  # destination_ref: 语义目标引用。
    intent_type: IntentType  # intent_type: 业务意图类型。
    intent_parameters: dict = field(default_factory=dict)  # intent_parameters: 业务参数。


@dataclass(frozen=True, slots=True)
class AgentSimulationDefinition:
    """一次 Agent 仿真(或测试模板)的完整定义;构造后不可变。"""

    simulation_id: str  # simulation_id: 仿真全局标识。
    agents: tuple[AgentSpawnDefinition, ...]  # agents: 固定 Agent 集合。
    plans: dict[str, tuple[AgentPlanStep, ...]] = field(default_factory=dict)  # plans: agent_id -> 有序计划(模板模式使用)。
    seed: int = 42  # seed: 随机种子,固定候选采样与 A* 平局规则。
    loop_policy: LoopPolicy = "stop"  # loop_policy: 计划耗尽后的行为。
    llm_mode: bool = False  # llm_mode: True=LLM 自动指挥;False=模板模式。

    def __post_init__(self) -> None:
        if not self.simulation_id:
            raise ValueError("simulation_id must not be empty")
        if not self.agents:
            raise ValueError("An agent simulation must contain at least one agent")
        agent_ids = [item.agent_id for item in self.agents]
        if len(agent_ids) != len(set(agent_ids)):
            raise ValueError("agent_id values must be unique")
        unknown_plans = [key for key in self.plans if key not in set(agent_ids)]
        if unknown_plans:
            raise ValueError(f"plans reference unknown agents: {unknown_plans}")

    @property
    def agent_count(self) -> int:
        """返回场景建立时冻结的 Agent 数量。"""

        return len(self.agents)


@dataclass(slots=True)
class AgentSnapshot:
    """单个 Agent 在指定 tick 的只读快照。"""

    agent_id: str
    role: str
    lifecycle_status: str  # lifecycle_status: 与 ran.AgentStatus 对齐:READY/ACTIVE/PAUSED/COMPLETED/FAILED。
    activity_state: str  # activity_state: planning/walking/network_active 等。
    position: tuple[float, float]  # position: 当前全局坐标。
    current_room_id: str | None = None  # current_room_id: 当前所在区域 ID。
    destination_id: str | None = None  # destination_id: 当前目标语义引用。
    current_intent_id: str | None = None  # current_intent_id: 当前意图 ID。
    waypoint_index: int = 0  # waypoint_index: 当前路径点序号。
    waypoint_count: int = 0  # waypoint_count: 路径点总数。
    last_transition_tick: int = 0  # last_transition_tick: 最近一次状态迁移 tick。
    error: str | None = None  # error: 最近错误信息。
    waypoints: list = field(default_factory=list)  # waypoints: 当前规划路径(世界坐标 [x, y] 列表),未规划时为空。

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "role": self.role,
            "lifecycle_status": self.lifecycle_status,
            "activity_state": self.activity_state,
            "position": list(self.position),
            "current_room_id": self.current_room_id,
            "destination_id": self.destination_id,
            "current_intent_id": self.current_intent_id,
            "waypoint_index": self.waypoint_index,
            "waypoint_count": self.waypoint_count,
            "last_transition_tick": self.last_transition_tick,
            "error": self.error,
            "waypoints": [list(point) for point in self.waypoints],
        }


@dataclass(slots=True)
class AgentStateFrame:
    """指定 tick 的全量 Agent 状态帧。"""

    simulation_id: str
    tick: int
    agents: list[AgentSnapshot] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "simulation_id": self.simulation_id,
            "tick": self.tick,
            "agents": [agent.to_dict() for agent in self.agents],
        }

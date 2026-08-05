"""Agent 子系统:LLM/模板引导 Agent 移动并产生网络意图。

模块边界:
- 契约与定义:contracts.py / definitions.py
- 计划来源:planning/(模板确定性、LLM 自动指挥)
- 导航:navigation/(语义索引、房间图、A*、碰撞、评分)
- 运行时:state_machine.py / runtime.py / registry.py
- RAN 对接:adapters/(状态只读适配、意图提交网关)
"""

from .contracts import (
    AgentPlan,
    AgentPlanStep,
    AgentSimulationDefinition,
    AgentSnapshot,
    AgentSpawnDefinition,
    AgentStateFrame,
)
from .definitions import (
    build_default_three_agent_definition,
    load_agent_simulation_definition,
)
from .registry import AgentRegistry
from .runtime import AgentRuntime
from .state_machine import AgentStateMachine

__all__ = [
    "AgentPlan",
    "AgentPlanStep",
    "AgentRegistry",
    "AgentRuntime",
    "AgentSimulationDefinition",
    "AgentSnapshot",
    "AgentSpawnDefinition",
    "AgentStateFrame",
    "AgentStateMachine",
    "build_default_three_agent_definition",
    "load_agent_simulation_definition",
]

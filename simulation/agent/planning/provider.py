"""计划提供者接口:决定"去哪里、做什么"。

实现约定:
- request_plan 返回语义计划(不含坐标);坐标合法性由导航层兜底。
- 返回 None 表示该 Agent 没有更多计划(模板耗尽或 LLM 结束信号)。
"""

from __future__ import annotations

from typing import Protocol

from ..contracts import AgentPlan


class AgentPlanProvider(Protocol):
    """Agent 计划来源:模板或 LLM。"""

    def request_plan(self, agent_id: str, context: dict) -> AgentPlan | None:
        """为指定 Agent 请求下一步计划。

        context: 调用方提供的只读上下文(如当前 tick、已完成意图数),供
        实现决定结束或循环策略。
        """
        ...

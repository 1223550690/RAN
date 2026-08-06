"""确定性模板计划提供者:按定义中的有序计划依次出队。

- 每个 Agent 独立游标,按 (destination_ref, intent_type) 顺序返回。
- 计划耗尽后:loop_policy="stop" 返回 None(Agent 结束);"repeat" 从头循环。
- 同一输入永远产生同一输出(可复现测量)。
"""

from __future__ import annotations

from ..contracts import AgentPlan, AgentSimulationDefinition


class TemplatePlanProvider:
    def __init__(self, definition: AgentSimulationDefinition) -> None:
        self.definition = definition
        self._cursors: dict[str, int] = {agent_id: 0 for agent_id in definition.plans}

    def request_plan(self, agent_id: str, context: dict) -> AgentPlan | None:
        steps = self.definition.plans.get(agent_id)
        if not steps:
            return None
        cursor = self._cursors.get(agent_id, 0)
        if cursor >= len(steps):
            if self.definition.loop_policy != "repeat":
                return None
            cursor = 0
        step = steps[cursor]
        self._cursors[agent_id] = cursor + 1
        return AgentPlan(
            agent_id=agent_id,
            destination_ref=step.destination_ref,
            intent_type=step.intent_type,
            intent_parameters=dict(step.intent_parameters),
            stay=step.stay,
        )

"""Deterministic template plan provider: dequeues the ordered plans from the definition one by one.

- Each agent has an independent cursor; plans are returned in (destination_ref, intent_type) order.
- When plans are exhausted: loop_policy="stop" returns None (agent ends); "repeat" loops from the start.
- The same input always produces the same output (reproducible measurements).
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

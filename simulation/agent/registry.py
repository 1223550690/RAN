"""AgentRegistry: freezes the agent set at scenario build time, providing runtime and snapshot access.

Agent IDs, roles, UEs, and the total count cannot be added to or removed after
construction; consistent with the uniqueness validation on the RAN side (RanScenarioDefinition).
"""

from __future__ import annotations

from .contracts import AgentSimulationDefinition, AgentStateFrame
from .adapters.ran_intent_gateway import RanIntentGateway
from .navigation import NavigationPlanner
from .planning import AgentPlanProvider
from .runtime import AgentRuntime


class AgentRegistry:
    def __init__(
        self,
        definition: AgentSimulationDefinition,
        *,
        plan_provider: AgentPlanProvider,
        navigation: NavigationPlanner,
        gateway: RanIntentGateway | None = None,
        speed_m_per_tick: float = 0.5,
        same_building_only: bool = False,
    ) -> None:
        self.definition = definition
        self.agent_ids = tuple(item.agent_id for item in definition.agents)
        self.ue_ids = tuple(
            item.ue_id or f"{item.agent_id}_phone" for item in definition.agents
        )
        if len(set(self.agent_ids)) != len(self.agent_ids):
            raise ValueError("agent_id values must be unique")
        if len(set(self.ue_ids)) != len(self.ue_ids):
            raise ValueError("ue_id values must be unique")
        self._runtimes = {
            item.agent_id: AgentRuntime(
                item,
                plan_provider=plan_provider,
                navigation=navigation,
                gateway=gateway,
                speed_m_per_tick=speed_m_per_tick,
                same_building_only=same_building_only,
            )
            for item in definition.agents
        }

    def attach_gateway(self, gateway: RanIntentGateway) -> None:
        """Attach the intent gateway after the RAN scenario is built (construction-order requirement, see orchestrator)."""

        for runtime in self._runtimes.values():
            runtime.gateway = gateway

    def runtimes(self) -> list[AgentRuntime]:
        return [self._runtimes[agent_id] for agent_id in self.agent_ids]

    def get(self, agent_id: str) -> AgentRuntime:
        return self._runtimes[agent_id]

    def step(self, tick: int) -> None:
        for runtime in self._runtimes.values():
            runtime.step(tick)

    def snapshot_frame(self, tick: int) -> AgentStateFrame:
        return AgentStateFrame(
            simulation_id=self.definition.simulation_id,
            tick=tick,
            agents=[runtime.to_snapshot(tick) for runtime in self.runtimes()],
        )

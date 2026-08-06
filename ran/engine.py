from __future__ import annotations

from ran.orchestration import AgentStateProvider, RanScenarioDefinition
from ran.scheduler import JavaSchedulerAdapter
from ran.scenario import MultiAgentRanScenario


class RanEngine:
    """Create and run a fixed-size multi-Agent RAN scenario."""

    def __init__(
        self,
        scene,
        scheduler=None,
        *,
        scenario_definition: RanScenarioDefinition | None = None,
        agent_state_provider: AgentStateProvider | None = None,
    ) -> None:
        self.scene = scene
        self.scheduler = scheduler or JavaSchedulerAdapter()
        self.scenario_definition = scenario_definition
        self.agent_state_provider = agent_state_provider

    def run_scenario(self, *, tick: int = 1, max_ticks: int = 5000) -> dict[str, object]:
        """Run the default or injected multi-Agent scenario until all services finish or the tick limit is reached."""

        scenario = self.build_scenario()
        state: dict[str, object] | None = None
        for offset in range(max(1, max_ticks)):
            state = scenario.step(tick + offset)
            if state.get("status") == "completed":
                break
        if state is None:
            raise RuntimeError("RAN aggregate mode did not execute")
        state["mode"] = "aggregate"
        return state

    def build_scenario(self) -> MultiAgentRanScenario:
        """Determine the total Agent count of the scenario here and build the collection-style orchestrator."""

        return MultiAgentRanScenario(
            self.scene,
            scheduler=self.scheduler,
            definition=self.scenario_definition,
            agent_state_provider=self.agent_state_provider,
        )

    def run_agent_upload_demo(self, *, tick: int = 1, max_ticks: int = 5000) -> dict[str, object]:
        """Compatibility entry point; actually runs the unified multi-Agent scenario."""

        return self.run_scenario(tick=tick, max_ticks=max_ticks)

    def build_upload_scenario(self) -> MultiAgentRanScenario:
        """Compatibility entry point; new code should call build_scenario()."""

        return self.build_scenario()

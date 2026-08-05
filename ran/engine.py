from __future__ import annotations

from ran.orchestration import AgentStateProvider, RanScenarioDefinition
from ran.scheduler import JavaSchedulerAdapter
from ran.scenario import MultiAgentRanScenario


class RanEngine:
    """创建并运行固定规模的多 Agent RAN 场景。"""

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
        """运行默认或注入的多 Agent 场景，直到全部业务结束或达到 tick 上限。"""

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
        """在此处确定场景 Agent 总数，并构造集合式编排器。"""

        return MultiAgentRanScenario(
            self.scene,
            scheduler=self.scheduler,
            definition=self.scenario_definition,
            agent_state_provider=self.agent_state_provider,
        )

    def run_agent_upload_demo(self, *, tick: int = 1, max_ticks: int = 5000) -> dict[str, object]:
        """兼容旧入口；实际运行统一的多 Agent 场景。"""

        return self.run_scenario(tick=tick, max_ticks=max_ticks)

    def build_upload_scenario(self) -> MultiAgentRanScenario:
        """兼容旧入口；新代码应调用 build_scenario()。"""

        return self.build_scenario()

"""SimulationOrchestrator:协调 Agent 子系统与 RAN 场景。

每 tick 流程:
1. 检查 RAN 业务终态,通知对应 Agent(NETWORK_ACTIVE → PLANNING)。
2. 推进所有 Agent(规划/移动/提交意图)。
3. 推进 RAN 场景(处理新提交的意图与活跃队列)。
4. 汇总 AgentStateFrame。

依赖顺序说明:registry 需要 gateway 才能提交意图,gateway 需要 scenario,
scenario 需要 registry 的状态适配器——因此 registry 先构建(gateway 后挂载),
scenario 使用 registry 的只读适配器,最后构建 gateway 并 attach 回 registry。
"""

from __future__ import annotations

from ran.contracts import AgentStateSnapshot
from ran.orchestration import build_runtime_agent_definition
from ran.scenario import MultiAgentRanScenario

from .agent import AgentRegistry, AgentSimulationDefinition
from .agent.adapters.ran_intent_gateway import RanIntentGateway
from .agent.adapters.ran_state_adapter import SimulationAgentStateProvider
from .agent.contracts import AgentStateFrame
from .agent.navigation import NavigationPlanner
from .agent.planning import AgentPlanProvider

TERMINAL_SERVICE_STATUSES = {"COMPLETED", "FAILED"}


class SimulationOrchestrator:
    def __init__(
        self,
        scene,
        *,
        agent_definition: AgentSimulationDefinition,
        plan_provider: AgentPlanProvider,
        scheduler=None,
        aliases: dict[str, str] | None = None,
        intent_profiles: dict | None = None,
        agent_radius: float = 0.5,
        speed_m_per_tick: float = 0.5,
        same_building_only: bool = False,
        tick_ms: float = 1000.0,
        seed: int | None = None,
    ) -> None:
        self.scene = scene
        self.agent_definition = agent_definition
        seed = seed if seed is not None else agent_definition.seed
        self.navigation = NavigationPlanner(
            scene,
            aliases=aliases,
            agent_radius=agent_radius,
            seed=seed,
        )
        # 1) 先建 registry(无 gateway),供状态适配器使用。
        self.registry = AgentRegistry(
            agent_definition,
            plan_provider=plan_provider,
            navigation=self.navigation,
            gateway=None,  # type: ignore[arg-type]
            speed_m_per_tick=speed_m_per_tick,
            same_building_only=same_building_only,
        )
        # 2) 建 RAN 场景,挂载只读状态适配器。
        ran_definition = build_runtime_agent_definition(
            agent_definition.simulation_id,
            list(zip(self.registry.agent_ids, self.registry.ue_ids)),
        )
        self.scenario = MultiAgentRanScenario(
            scene,
            scheduler=scheduler,
            definition=ran_definition,
            agent_state_provider=SimulationAgentStateProvider(self.registry),
            tick_ms=tick_ms,
        )
        # 3) 建意图网关并挂载回 registry。
        self.gateway = RanIntentGateway(self.scenario, intent_profiles=intent_profiles)
        self.registry.attach_gateway(self.gateway)
        self._service_prev_status: dict[str, str] = {}
        self.ran_state: dict | None = None

    # ------------------------------------------------------------------ tick 推进

    def step(self, tick: int) -> AgentStateFrame:
        self._notify_terminal_services(tick)
        self.registry.step(tick)
        self.ran_state = self.scenario.step(tick)
        return self.registry.snapshot_frame(tick)

    def _notify_terminal_services(self, tick: int) -> None:
        """检测 RAN 业务进入终态,通知对应 Agent 回到 PLANNING。"""

        for service_id, service in list(self.scenario.services.items()):
            status = service.status
            prev = self._service_prev_status.get(service_id)
            self._service_prev_status[service_id] = status
            if status in TERMINAL_SERVICE_STATUSES and prev not in TERMINAL_SERVICE_STATUSES:
                try:
                    runtime = self.registry.get(service.agent_id)
                except KeyError:
                    continue
                runtime.on_intent_terminal(
                    service.intent_id,
                    succeeded=(status == "COMPLETED"),
                    tick=tick,
                )

    # ------------------------------------------------------------------ 状态接口

    def get_agent_states(self, *, tick: int) -> list[AgentStateSnapshot]:
        """实现 ran AgentStateProvider 兼容的只读快照接口(无副作用)。"""

        return SimulationAgentStateProvider(self.registry).get_agent_states(tick=tick)

    def snapshot(self, tick: int) -> AgentStateFrame:
        """当前 Agent 状态帧,不推进仿真。"""

        return self.registry.snapshot_frame(tick)

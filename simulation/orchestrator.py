"""SimulationOrchestrator: coordinates the agent subsystem with the RAN scenario.

Per-tick flow:
1. Check RAN service terminal states and notify the corresponding agents (NETWORK_ACTIVE -> PLANNING).
2. Advance all agents (planning/moving/submitting intents).
3. Advance the RAN scenario (process newly submitted intents and active queues).
4. Aggregate the AgentStateFrame.

Dependency order: the registry needs the gateway to submit intents, the gateway needs the scenario,
and the scenario needs the registry's state adapter - so the registry is built first (gateway attached later),
the scenario uses the registry's read-only adapter, and finally the gateway is built and attached back to the registry.
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


def _intent_direction(intent_type: str) -> str:
    """Intent type -> transport direction (DL for downlink-type intents, UL otherwise)."""

    if intent_type in ("video_download", "file_download", "web_browse", "game_download"):
        return "DL"
    return "UL"


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
        n3_bandwidth_mbps: float | None = None,
        max_waiting_ticks: int = 600,
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
        # 1) Build the registry first (without a gateway) for the state adapter to use.
        self.registry = AgentRegistry(
            agent_definition,
            plan_provider=plan_provider,
            navigation=self.navigation,
            gateway=None,  # type: ignore[arg-type]
            speed_m_per_tick=speed_m_per_tick,
            same_building_only=same_building_only,
        )
        # 2) Build the RAN scenario and attach the read-only state adapter.
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
            n3_bandwidth_mbps=n3_bandwidth_mbps,
            max_waiting_ticks=max_waiting_ticks,
        )
        # 3) Build the intent gateway and attach it back to the registry.
        self.gateway = RanIntentGateway(self.scenario, intent_profiles=intent_profiles)
        self.registry.attach_gateway(self.gateway)
        self._service_prev_status: dict[str, str] = {}
        self.ran_state: dict | None = None

    # ------------------------------------------------------------------ tick progression

    def step(self, tick: int) -> AgentStateFrame:
        self._notify_terminal_services(tick)
        self.registry.step(tick)
        self.ran_state = self.scenario.step(tick)
        frame = self.registry.snapshot_frame(tick)
        frame.plan_summary = self._build_plan_summary()
        return frame

    def _build_plan_summary(self) -> list[dict]:
        """Static task list (template mode): each agent's ordered tasks (type/direction/index/total).

        The frontend task panel renders the task list from this; dynamic progress is aligned via ran_state.service_states.
        """

        summary: list[dict] = []
        for agent_id, steps in (self.agent_definition.plans or {}).items():
            total = len(steps)
            for index, step in enumerate(steps):
                summary.append(
                    {
                        "agent_id": agent_id,
                        "intent_type": step.intent_type,
                        "direction": _intent_direction(step.intent_type),
                        "index": index,
                        "total": total,
                    }
                )
        return summary

    def _notify_terminal_services(self, tick: int) -> None:
        """Detect RAN services entering a terminal state and notify the corresponding agent back to PLANNING."""

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

    # ------------------------------------------------------------------ state interface

    def get_agent_states(self, *, tick: int) -> list[AgentStateSnapshot]:
        """Implement the read-only snapshot interface compatible with ran AgentStateProvider (side-effect free)."""

        return SimulationAgentStateProvider(self.registry).get_agent_states(tick=tick)

    def snapshot(self, tick: int) -> AgentStateFrame:
        """Current agent state frame without advancing the simulation."""

        return self.registry.snapshot_frame(tick)

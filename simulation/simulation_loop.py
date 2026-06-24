from __future__ import annotations

import time

from agents.decision import AgentDecisionController
from agents.mobility import MobilityController
from .clock import SimulationClock
from .state import SimulationState


class SimulationLoop:
    def __init__(
        self,
        state: SimulationState,
        *,
        clock: SimulationClock,
        preview_service=None,
        decision_controller: AgentDecisionController | None = None,
        seed: int = 7,
    ) -> None:
        self.state = state
        self.clock = clock
        self.mobility = MobilityController(state.scene, seed=seed)
        self.preview_service = preview_service
        self.decision_controller = decision_controller
        self.console: list[str] = []

    def run(self, total_ticks: int) -> None:
        self.log("simulation started")
        self.write_preview_state(now_seconds=0.0)
        for _ in range(total_ticks):
            self.state.tick = self.clock.step()
            now_seconds = self.state.tick * self.clock.tick_ms / 1000
            for agent in self.state.agents:
                llm_enabled = self.decision_controller is not None and self.decision_controller.enabled
                if self.decision_controller is not None:
                    did_decide = self.decision_controller.maybe_decide(
                        agent=agent,
                        scene=self.state.scene,
                        now_seconds=now_seconds,
                    )
                    if did_decide:
                        self.log(
                            f"tick={self.state.tick} llm_decision agent={agent.name} "
                            f"behavior={agent.behavior} next_call_in={agent.llm_wait_seconds(now_seconds):.1f}s"
                        )
                self.mobility.step(agent, allow_random_target=not llm_enabled, now_seconds=now_seconds)
            line = self.format_tick()
            self.log(line)
            self.write_preview_state(now_seconds=now_seconds)
            print(line, flush=True)
            time.sleep(self.clock.tick_ms / 1000)

    def write_preview_state(self, *, now_seconds: float) -> None:
        if self.preview_service is not None:
            self.preview_service.write_state(
                tick=self.state.tick,
                now_seconds=now_seconds,
                scene=self.state.scene,
                agents=self.state.agents,
                console=self.console,
            )

    def format_tick(self) -> str:
        parts = []
        now_seconds = self.state.tick * self.clock.tick_ms / 1000
        for agent in self.state.agents:
            x, y = agent.position
            reason = f" reason={agent.decision_reason}" if agent.decision_reason else ""
            llm = ""
            if agent.llm_enabled:
                llm = f" llm_next={agent.llm_wait_seconds(now_seconds):.1f}s"
            parts.append(f"{agent.name}@({x:.2f},{y:.2f}) {agent.behavior}{llm}{reason}")
        return f"tick={self.state.tick} | " + " | ".join(parts)

    def log(self, message: str) -> None:
        self.console.append(message)
        if len(self.console) > 120:
            del self.console[:-120]

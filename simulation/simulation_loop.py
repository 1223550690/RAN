from __future__ import annotations

import time

from .clock import SimulationClock
from .state import SimulationState


class SimulationLoop:
    def __init__(
        self,
        state: SimulationState,
        *,
        clock: SimulationClock,
        preview_service=None,
    ) -> None:
        self.state = state
        self.clock = clock
        self.preview_service = preview_service
        self.console: list[str] = []

    def run(self, total_ticks: int) -> None:
        self.log("simulation started")
        self.write_preview_state(now_seconds=0.0)
        for _ in range(total_ticks):
            self.state.tick = self.clock.step()
            now_seconds = self.state.tick * self.clock.tick_ms / 1000
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
                agents=[],
                ran_requests=[],
                console=self.console,
            )

    def format_tick(self) -> str:
        return f"tick={self.state.tick} | agent_input=disabled"

    def log(self, message: str) -> None:
        self.console.append(message)
        if len(self.console) > 120:
            del self.console[:-120]

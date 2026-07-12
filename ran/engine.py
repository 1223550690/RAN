from __future__ import annotations

from ran.scheduler import JavaSchedulerAdapter
from ran.scenario import RanUploadScenario


class RanEngine:
    """Project implementation detail."""

    def __init__(self, scene, scheduler=None) -> None:
        self.scene = scene
        self.scheduler = scheduler or JavaSchedulerAdapter()

    def run_agent_upload_demo(self, *, tick: int = 1, max_ticks: int = 5000) -> dict[str, object]:
        """Project implementation detail."""

        scenario = RanUploadScenario(self.scene, scheduler=self.scheduler)
        state: dict[str, object] | None = None
        for offset in range(max(1, max_ticks)):
            state = scenario.step(tick + offset)
            if state.get("status") == "completed":
                break
        if state is None:
            raise RuntimeError("RAN MVP aggregate mode did not execute")
        state["mode"] = "aggregate"
        return state

    def build_upload_scenario(self) -> RanUploadScenario:
        """Project implementation detail."""

        return RanUploadScenario(self.scene, scheduler=self.scheduler)

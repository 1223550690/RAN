from __future__ import annotations

from ran.scheduler import JavaSchedulerAdapter
from ran.scenario import RanUploadScenario


class RanEngine:
    """Project implementation detail."""

    def __init__(self, scene, scheduler=None) -> None:
        self.scene = scene
        self.scheduler = scheduler or JavaSchedulerAdapter()

    def run_agent_upload_demo(self, *, tick: int = 1, max_ticks: int = 5000) -> list[dict[str, object]]:
        """Project implementation detail."""

        scenario = RanUploadScenario(self.scene, scheduler=self.scheduler)
        states: list[dict[str, object]] | None = None
        for offset in range(max(1, max_ticks)):
            states = scenario.step(tick + offset)
            if states[0].get("status") == "completed":
                break
        if states[0] is None:
            raise RuntimeError("RAN MVP aggregate mode did not execute")
        states[0]["mode"] = "aggregate"
        return states

    def build_upload_scenario(self) -> RanUploadScenario:
        """Project implementation detail."""

        return RanUploadScenario(self.scene, scheduler=self.scheduler)

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SimulationState:
    scene: object
    ran_requests: list[dict] = field(default_factory=list)
    tick: int = 0

    def to_dict(self) -> dict:
        return {
            "tick": self.tick,
            "scene": self.scene.to_dict(),
            "agents": [],
            "ran_requests": list(self.ran_requests),
        }

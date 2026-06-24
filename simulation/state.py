from __future__ import annotations

from dataclasses import dataclass

from agents.agent import AgentState


@dataclass
class SimulationState:
    scene: object
    agents: list[AgentState]
    tick: int = 0

    def to_dict(self) -> dict:
        return {
            "tick": self.tick,
            "scene": self.scene.to_dict(),
            "agents": [agent.to_dict() for agent in self.agents],
        }

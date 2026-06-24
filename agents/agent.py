from __future__ import annotations

from dataclasses import dataclass, field


Point = tuple[float, float]


@dataclass
class AgentState:
    agent_id: str
    name: str
    position: Point
    area_id: str | None = None
    behavior: str = "idle"
    target: Point | None = None
    target_area_id: str | None = None
    target_element_id: str | None = None
    color: str = "#7f4ac9"
    speed: float = 0.12
    behavior_started_at: float | None = None
    behavior_ends_at: float | None = None
    last_llm_call_at: float | None = None
    next_llm_call_at: float | None = None
    decision_reason: str | None = None
    llm_enabled: bool = False
    metadata: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "position": [self.position[0], self.position[1]],
            "area_id": self.area_id,
            "behavior": self.behavior,
            "target": [self.target[0], self.target[1]] if self.target else None,
            "target_area_id": self.target_area_id,
            "target_element_id": self.target_element_id,
            "color": self.color,
            "speed": self.speed,
            "behavior_started_at": self.behavior_started_at,
            "behavior_ends_at": self.behavior_ends_at,
            "last_llm_call_at": self.last_llm_call_at,
            "next_llm_call_at": self.next_llm_call_at,
            "decision_reason": self.decision_reason,
            "llm_enabled": self.llm_enabled,
            "metadata": dict(self.metadata),
        }

    def llm_wait_seconds(self, now_seconds: float) -> float:
        if self.next_llm_call_at is None:
            return 0.0
        return max(0.0, self.next_llm_call_at - now_seconds)

from __future__ import annotations

from dataclasses import dataclass

from .agent import AgentState
from .behavior import behavior_for_area
from .llm_client import DeepSeekAPIError, DeepSeekClient


@dataclass
class AgentDecision:
    behavior: str
    target_area_id: str | None = None
    target_element_id: str | None = None
    duration_seconds: float = 30.0
    reason: str = ""


class AgentDecisionController:
    def __init__(
        self,
        client: DeepSeekClient,
        *,
        cooldown_seconds: float = 30.0,
        min_duration_seconds: float = 8.0,
        max_duration_seconds: float = 180.0,
    ) -> None:
        self.client = client
        self.cooldown_seconds = cooldown_seconds
        self.min_duration_seconds = min_duration_seconds
        self.max_duration_seconds = max_duration_seconds

    @property
    def enabled(self) -> bool:
        return self.client.enabled

    def maybe_decide(self, *, agent: AgentState, scene, now_seconds: float) -> bool:
        agent.llm_enabled = self.enabled
        if not self.enabled:
            return False

        if agent.behavior_ends_at is not None and now_seconds < agent.behavior_ends_at:
            return False

        if agent.next_llm_call_at is not None and now_seconds < agent.next_llm_call_at:
            if agent.target is None:
                agent.behavior = "idle_waiting_llm_cooldown"
            return False

        agent.last_llm_call_at = now_seconds
        try:
            decision = self.request_decision(agent=agent, scene=scene, now_seconds=now_seconds)
        except DeepSeekAPIError as exc:
            agent.behavior = "llm_error_fallback"
            agent.decision_reason = str(exc)
            agent.next_llm_call_at = now_seconds + self.cooldown_seconds
            agent.metadata["llm_error"] = str(exc)
            return False

        self.apply_decision(agent=agent, scene=scene, decision=decision, now_seconds=now_seconds)
        return True

    def request_decision(self, *, agent: AgentState, scene, now_seconds: float) -> AgentDecision:
        payload = self.client.chat_json(
            [
                {"role": "system", "content": self.system_prompt()},
                {"role": "user", "content": self.user_prompt(agent=agent, scene=scene, now_seconds=now_seconds)},
            ]
        )
        return AgentDecision(
            behavior=str(payload.get("behavior") or "interacting"),
            target_area_id=clean_optional(payload.get("target_area_id")),
            target_element_id=clean_optional(payload.get("target_element_id")),
            duration_seconds=to_float(payload.get("duration_seconds"), default=30.0),
            reason=str(payload.get("reason") or ""),
        )

    def apply_decision(self, *, agent: AgentState, scene, decision: AgentDecision, now_seconds: float) -> None:
        duration = clamp(decision.duration_seconds, self.min_duration_seconds, self.max_duration_seconds)
        area = find_area(scene, decision.target_area_id) if decision.target_area_id else None
        element_result = find_element(scene, decision.target_element_id) if decision.target_element_id else None

        if element_result is not None:
            area, element = element_result
            agent.target = tuple(element.center)
            agent.target_area_id = area.node_id
            agent.target_element_id = element.node_id
            agent.metadata["target_element_name"] = element.name
        elif area is not None:
            agent.target = area_center(area)
            agent.target_area_id = area.node_id
            agent.target_element_id = None
            agent.metadata.pop("target_element_name", None)
        else:
            agent.target = None
            agent.target_area_id = None
            agent.target_element_id = None

        agent.behavior = decision.behavior or behavior_for_area(agent.target_area_id or agent.area_id)
        agent.behavior_started_at = now_seconds
        agent.behavior_ends_at = now_seconds + duration
        agent.next_llm_call_at = agent.behavior_ends_at + self.cooldown_seconds
        agent.decision_reason = decision.reason

    def system_prompt(self) -> str:
        return (
            "You control one simulated human Agent in a 2D indoor scene. "
            "Choose the next concrete behavior after the previous behavior has ended. "
            "Do not invent area IDs or element IDs. Output strict json only. "
            "JSON format: {"
            '"behavior":"short_action_name",'
            '"target_area_id":"area id or null",'
            '"target_element_id":"element id or null",'
            '"duration_seconds":30,'
            '"reason":"short reason"'
            "}."
        )

    def user_prompt(self, *, agent: AgentState, scene, now_seconds: float) -> str:
        areas = []
        for area in scene.areas:
            elements = [
                {
                    "id": element.node_id,
                    "name": element.name,
                    "movable": element.movable,
                    "blocks_movement": element.blocks_movement,
                }
                for element in area.elements[:8]
            ]
            areas.append({"id": area.node_id, "name": area.name, "elements": elements})

        return (
            "Return json for the next Agent behavior.\n"
            f"scene_id={scene.node_id}, scene_name={scene.name}\n"
            f"now_seconds={now_seconds:.1f}\n"
            f"agent_id={agent.agent_id}, name={agent.name}, position={agent.position}, "
            f"area_id={agent.area_id}, current_behavior={agent.behavior}\n"
            f"available_areas_and_elements={areas}\n"
            "Prefer a target_area_id and optionally one valid target_element_id."
        )


def clean_optional(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() == "null":
        return None
    return text


def to_float(value, *, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def find_area(scene, area_id: str | None):
    if area_id is None:
        return None
    for area in scene.areas:
        if area.node_id == area_id:
            return area
    return None


def find_element(scene, element_id: str | None):
    if element_id is None:
        return None
    for area in scene.areas:
        for element in area.elements:
            if element.node_id == element_id:
                return area, element
    return None


def area_center(area) -> tuple[float, float]:
    min_x, min_y, max_x, max_y = area.bounds
    return (round((min_x + max_x) / 2, 4), round((min_y + max_y) / 2, 4))

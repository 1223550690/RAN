from __future__ import annotations

import math
import random

from .agent import AgentState, Point
from .behavior import behavior_for_area


class MobilityController:
    def __init__(self, scene, *, seed: int = 7) -> None:
        self.scene = scene
        self.rng = random.Random(seed)

    def step(self, agent: AgentState, *, allow_random_target: bool = True, now_seconds: float | None = None) -> None:
        if agent.target is None:
            if allow_random_target:
                self.assign_new_target(agent)
            else:
                return

        if agent.target is None:
            agent.behavior = behavior_for_area(agent.area_id)
            return

        next_position, arrived = move_towards(agent.position, agent.target, agent.speed)
        agent.position = next_position
        agent.area_id = find_area_id(self.scene, agent.position)

        if arrived:
            agent.position = agent.target
            agent.area_id = find_area_id(self.scene, agent.position) or agent.target_area_id
            agent.target = None
            agent.target_area_id = None
            agent.target_element_id = None
            if now_seconds is None or agent.behavior_ends_at is None or now_seconds >= agent.behavior_ends_at:
                agent.behavior = behavior_for_area(agent.area_id)
        else:
            agent.behavior = "walking"

    def assign_new_target(self, agent: AgentState) -> None:
        areas = list(getattr(self.scene, "areas", []))
        if not areas:
            return

        area = self.rng.choice(areas)
        agent.target_area_id = area.node_id
        agent.target = random_point_in_bounds(area.bounds, self.rng)

        if area.elements:
            element = self.rng.choice(area.elements)
            agent.target_element_id = element.node_id
            agent.metadata["target_element_name"] = element.name


def move_towards(position: Point, target: Point, speed: float) -> tuple[Point, bool]:
    dx = target[0] - position[0]
    dy = target[1] - position[1]
    distance = math.hypot(dx, dy)
    if distance <= speed or distance == 0:
        return target, True
    ratio = speed / distance
    return (round(position[0] + dx * ratio, 4), round(position[1] + dy * ratio, 4)), False


def random_point_in_bounds(bounds: tuple[float, float, float, float], rng: random.Random) -> Point:
    min_x, min_y, max_x, max_y = bounds
    margin_x = min(0.35, max(0.0, (max_x - min_x) / 4))
    margin_y = min(0.35, max(0.0, (max_y - min_y) / 4))
    return (
        round(rng.uniform(min_x + margin_x, max_x - margin_x), 4),
        round(rng.uniform(min_y + margin_y, max_y - margin_y), 4),
    )


def find_area_id(scene, position: Point) -> str | None:
    x, y = position
    for area in getattr(scene, "areas", []):
        min_x, min_y, max_x, max_y = area.bounds
        if min_x <= x <= max_x and min_y <= y <= max_y:
            return area.node_id
    return None

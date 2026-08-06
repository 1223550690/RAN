"""Candidate endpoint sampling: sample up to max_candidates valid endpoints around a target area/element.

Strategy:
- Area target: grid sampling inside the area + area center + midpoints of doors leading into the area.
- Element target: four sides of the element (front/back/left/right, distance = half size + agent radius + margin) + element center (when the element does not block).
- Portal target: door midpoint.

The sampling order is determined by a fixed seed, guaranteeing reproducibility.
"""

from __future__ import annotations

import random

from .geometry import Point, Rect
from .semantic_index import ResolvedDestination
from .walkability import WalkabilityMap


class EndpointSampler:
    def __init__(self, walkability: WalkabilityMap, *, max_candidates: int = 48, seed: int = 42) -> None:
        self.walkability = walkability
        self.max_candidates = max_candidates
        self.rng = random.Random(seed)

    def sample(self, destination: ResolvedDestination) -> list[Point]:
        """Return the candidate endpoint list (infeasible points filtered; order determined by the seed)."""

        if destination.target_type == "portal":
            candidates = [destination.position]
        elif destination.target_type == "element":
            candidates = self._sample_element(destination)
        else:
            candidates = self._sample_area(destination)
        # Add midpoints of doors from the target area to other areas so cross-room endpoints stay close to doors.
        candidates.extend(self._door_approaches(destination))
        seen: set[tuple[float, float]] = set()
        result: list[Point] = []
        self.rng.shuffle(candidates)
        for candidate in candidates:
            key = (round(candidate[0], 4), round(candidate[1], 4))
            if key in seen:
                continue
            seen.add(key)
            if self.walkability.point_clear(candidate):
                result.append(candidate)
            if len(result) >= self.max_candidates:
                break
        return result

    def _sample_area(self, destination: ResolvedDestination) -> list[Point]:
        bounds = destination.bounds
        if bounds is None:
            return [destination.position]
        min_x, min_y, max_x, max_y = bounds
        width, height = max_x - min_x, max_y - min_y
        step = max(self.walkability.agent_radius * 2.0, width / 6.0, height / 6.0)
        candidates: list[Point] = [destination.position]
        x = min_x + step / 2
        while x < max_x:
            y = min_y + step / 2
            while y < max_y:
                candidates.append((x, y))
                y += step
            x += step
        return candidates

    def _sample_element(self, destination: ResolvedDestination) -> list[Point]:
        bounds = destination.bounds
        center = destination.position
        if bounds is None:
            return [center]
        half_w = max(0.1, (bounds[2] - bounds[0]) / 2)
        half_h = max(0.1, (bounds[3] - bounds[1]) / 2)
        margin = self.walkability.agent_radius * 2.0
        return [
            (center[0], center[1] - half_h - margin),  # top side
            (center[0], center[1] + half_h + margin),  # bottom side
            (center[0] - half_w - margin, center[1]),  # left side
            (center[0] + half_w + margin, center[1]),  # right side
            center,  # center (usable when the element does not block)
        ]

    def _door_approaches(self, destination: ResolvedDestination) -> list[Point]:
        """Midpoints of doors on the target area boundary leading to other areas (keeps endpoints near doors when crossing rooms)."""

        if destination.target_type != "area":
            return []
        area_id = destination.target_id
        approaches: list[Point] = []
        for portal in self.walkability.index.portals.values():
            if not portal.open:
                continue
            if area_id in portal.area_ids:
                approaches.append(portal.center)
        return approaches

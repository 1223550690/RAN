"""Candidate route scoring.

P1 metrics (all computed, weighted summary):
- length: total route length (meters).
- avg_clearance / min_clearance: average/minimum distance from path sample points to the nearest obstacle.
- wall_ratio: fraction of sample points "hugging the wall" (nearest obstacle < 2 * agent_radius).
- endpoint_space: fraction of standable space around the endpoint (8-direction sampling).
- front_center / reachable: whether the target is at the element's front center / within arm's reach (recorded, weight 0).

Lower composite score is better: score = length + wall_ratio * WALL_PENALTY + max(0, REF - min_clearance) - endpoint_space * ENDPOINT_BONUS.
"""

from __future__ import annotations

from dataclasses import dataclass

from .geometry import Point, Rect
from .semantic_index import ResolvedDestination
from .walkability import WalkabilityMap

WALL_PENALTY = 3.0  # penalty per 1.0 increase of wall_ratio (meters).
CLEARANCE_REF = 0.8  # minimum clearance reference (meters); the amount below it is penalized.
ENDPOINT_BONUS = 1.2  # bonus per 1.0 of endpoint standable-space ratio (meters).
ARM_REACH_M = 1.0  # arm-reach distance reference (meters).


@dataclass(frozen=True, slots=True)
class RouteScore:
    length: float  # length: total route length (meters).
    avg_clearance: float  # avg_clearance: average clearance (meters).
    min_clearance: float  # min_clearance: minimum clearance (meters).
    wall_ratio: float  # wall_ratio: fraction of wall-hugging sample points [0,1].
    endpoint_space: float  # endpoint_space: standable-space ratio around the endpoint [0,1].
    front_center: bool  # front_center: whether the endpoint is at the target's front center (approx: endpoint on a cardinal direction from the target center).
    reachable: bool  # reachable: whether the endpoint is within arm's reach.
    score: float  # score: composite score; lower is better.


def score_route(
    waypoints: list[Point],
    walkability: WalkabilityMap,
    destination: ResolvedDestination,
) -> RouteScore:
    if len(waypoints) < 2:
        return RouteScore(
            length=0.0,
            avg_clearance=0.0,
            min_clearance=0.0,
            wall_ratio=1.0,
            endpoint_space=0.0,
            front_center=False,
            reachable=False,
            score=float("inf"),
        )

    length = sum(
        ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5
        for a, b in zip(waypoints, waypoints[1:])
    )
    samples = _sample_along_path(waypoints, max(5, min(40, len(waypoints) * 3)))
    clearances = [walkability.point_to_nearest_obstacle(point) for point in samples]
    avg_clearance = sum(clearances) / len(clearances)
    min_clearance = min(clearances)
    wall_threshold = walkability.agent_radius * 2.0
    wall_ratio = sum(1.0 for value in clearances if value < wall_threshold) / len(clearances)

    endpoint_space = _endpoint_space(walkability, waypoints[-1])
    front_center = _is_front_center(waypoints[-1], destination)
    reachable = _is_reachable(waypoints[-1], destination)

    score = (
        length
        + wall_ratio * WALL_PENALTY
        + max(0.0, CLEARANCE_REF - min_clearance)
        - endpoint_space * ENDPOINT_BONUS
    )
    return RouteScore(
        length=length,
        avg_clearance=avg_clearance,
        min_clearance=min_clearance,
        wall_ratio=wall_ratio,
        endpoint_space=endpoint_space,
        front_center=front_center,
        reachable=reachable,
        score=score,
    )


def _sample_along_path(waypoints: list[Point], count: int) -> list[Point]:
    if len(waypoints) == 1:
        return [waypoints[0]]
    total = sum(
        ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5
        for a, b in zip(waypoints, waypoints[1:])
    )
    if total <= 0:
        return [waypoints[0]] * count
    samples: list[Point] = []
    target_dist = 0.0
    step_dist = total / max(1, count - 1)
    segment_start = waypoints[0]
    accumulated = 0.0
    for segment_end in waypoints[1:]:
        segment_length = ((segment_end[0] - segment_start[0]) ** 2 + (segment_end[1] - segment_start[1]) ** 2) ** 0.5
        while target_dist <= accumulated + segment_length and len(samples) < count:
            ratio = (target_dist - accumulated) / segment_length if segment_length > 0 else 0.0
            samples.append(
                (
                    segment_start[0] + (segment_end[0] - segment_start[0]) * ratio,
                    segment_start[1] + (segment_end[1] - segment_start[1]) * ratio,
                )
            )
            target_dist += step_dist
        accumulated += segment_length
        segment_start = segment_end
    while len(samples) < count:
        samples.append(waypoints[-1])
    return samples[:count]


def _endpoint_space(walkability: WalkabilityMap, endpoint: Point) -> float:
    radius = walkability.agent_radius * 2.0
    directions = (
        (1, 0),
        (-1, 0),
        (0, 1),
        (0, -1),
        (1, 1),
        (1, -1),
        (-1, 1),
        (-1, -1),
    )
    if not walkability.point_clear(endpoint):
        return 0.0
    clear_count = 0
    for dx, dy in directions:
        probe = (endpoint[0] + dx * radius, endpoint[1] + dy * radius)
        if walkability.point_clear(probe):
            clear_count += 1
    return clear_count / len(directions)


def _is_front_center(endpoint: Point, destination: ResolvedDestination) -> bool:
    if destination.target_type != "element" or destination.bounds is None:
        return False
    bounds: Rect = destination.bounds
    center = destination.position
    # Approximation: the endpoint is directly above/below/left/right of the element center, in the corresponding half-plane of the center.
    dx = endpoint[0] - center[0]
    dy = endpoint[1] - center[1]
    if abs(dx) < 1e-6 and abs(dy) < 1e-6:
        return False
    half_w = (bounds[2] - bounds[0]) / 2
    half_h = (bounds[3] - bounds[1]) / 2
    return (abs(dx) > half_w and abs(dy) <= half_h) or (abs(dy) > half_h and abs(dx) <= half_w)


def _is_reachable(endpoint: Point, destination: ResolvedDestination) -> bool:
    if destination.target_type != "element":
        return False
    dx = endpoint[0] - destination.position[0]
    dy = endpoint[1] - destination.position[1]
    return (dx * dx + dy * dy) ** 0.5 <= ARM_REACH_M + 0.5

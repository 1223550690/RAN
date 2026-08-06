"""Path smoothing: line-of-sight simplification + minimum-spacing filtering.

- Line-of-sight simplification: if the straight segment from waypoint[i] to waypoint[j] is passable, skip the intermediate points.
- Minimum-spacing filtering: drop intermediate points that are too close to their neighbors (keep first and last).
"""

from __future__ import annotations

from .geometry import Point
from .walkability import WalkabilityMap


def smooth_path(
    waypoints: list[Point],
    walkability: WalkabilityMap,
    *,
    min_spacing: float = 0.15,
    max_lookahead: int = 64,
) -> list[Point]:
    if len(waypoints) < 3:
        return list(waypoints)

    # Line-of-sight simplification.
    simplified: list[Point] = [waypoints[0]]
    i = 0
    while i < len(waypoints) - 1:
        j = min(len(waypoints) - 1, i + max_lookahead)
        while j > i + 1:
            if walkability.segment_clear(waypoints[i], waypoints[j]):
                break
            j -= 1
        simplified.append(waypoints[j])
        i = j

    # Minimum-spacing filtering (keep first and last).
    filtered: list[Point] = [simplified[0]]
    for point in simplified[1:-1]:
        if ((point[0] - filtered[-1][0]) ** 2 + (point[1] - filtered[-1][1]) ** 2) ** 0.5 >= min_spacing:
            filtered.append(point)
    if len(simplified) > 1:
        filtered.append(simplified[-1])
    return filtered


def push_away_from_walls(
    waypoints: list[Point],
    walkability: WalkabilityMap,
    *,
    target_clearance: float = 0.6,
    max_shift: float = 0.9,
    steps: int = 9,
) -> list[Point]:
    """Push intermediate waypoints away from the nearest wall, keeping at least target_clearance margin.

    - First/last points stay put (the start is the actual position, the end is the goal point).
    - Best effort: if pushing makes the segments to neighboring points impassable (e.g. narrow passages/door openings),
      keep the original position (the original position is passable per A*/smoothing, just with less margin).
    - Stepwise approach: advance max_shift/steps at a time and take the first candidate where the point
      is standable AND the segments to the previous/next points are passable.
    """

    if len(waypoints) < 3:
        return list(waypoints)

    step_shift = max_shift / steps
    result: list[Point] = [waypoints[0]]
    for index in range(1, len(waypoints) - 1):
        point = waypoints[index]
        distance, direction = walkability.clearance_and_direction(point)
        if distance >= target_clearance:
            result.append(point)
            continue
        next_point = waypoints[index + 1]
        prev = result[-1]
        shifted = point
        for shift_step in range(1, steps + 1):
            shift = shift_step * step_shift
            candidate = (point[0] + direction[0] * shift, point[1] + direction[1] * shift)
            if not walkability.point_clear(candidate):
                break
            if walkability.segment_clear(prev, candidate) and walkability.segment_clear(candidate, next_point):
                shifted = candidate
                break
        result.append(shifted)
    result.append(waypoints[-1])
    return result

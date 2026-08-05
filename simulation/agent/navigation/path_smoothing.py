"""路径平滑:视线简化 + 最小间距过滤。

- 视线简化:若 waypoint[i] 到 waypoint[j] 的直线段可通行,跳过中间点。
- 最小间距过滤:相邻点距离过近时删除中间点(保留首尾)。
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

    # 视线简化。
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

    # 最小间距过滤(保留首尾)。
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
    """将中间路径点沿"远离最近墙"方向推出,保持至少 target_clearance 余量。

    - 首尾点不动(起点是实际位置,终点是目标点)。
    - 尽力而为:若推动后与相邻点的线段不可通行(如窄通道/门开口),保留原位置
      (原位置由 A*/平滑保证可通行,只是余量较小)。
    - 分步逼近:每次推进 max_shift/steps,取第一个同时满足"点可站立"且
      "与前后线段可通行"的候选。
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

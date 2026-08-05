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

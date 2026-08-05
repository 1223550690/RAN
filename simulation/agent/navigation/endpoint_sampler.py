"""候选终点采样:在目标区域/元素周围采样最多 max_candidates 个合法终点。

策略:
- 区域目标:区域内部按网格采样 + 区域中心 + 通向该区域的门中点。
- 元素目标:元素四侧(正面/背面/左右,距离 = 半尺寸 + Agent 半径 + 间距)+ 元素中心(元素不阻挡时)。
- 门目标:门中点。

采样顺序由固定种子决定,保证可复现。
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
        """返回候选终点列表(已过滤不可行点,顺序由种子决定)。"""

        if destination.target_type == "portal":
            candidates = [destination.position]
        elif destination.target_type == "element":
            candidates = self._sample_element(destination)
        else:
            candidates = self._sample_area(destination)
        # 加入目标区域通往其他区域的门中点,便于跨房间终点靠近门。
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
            (center[0], center[1] - half_h - margin),  # 上侧
            (center[0], center[1] + half_h + margin),  # 下侧
            (center[0] - half_w - margin, center[1]),  # 左侧
            (center[0] + half_w + margin, center[1]),  # 右侧
            center,  # 中心(元素不阻挡时可用)
        ]

    def _door_approaches(self, destination: ResolvedDestination) -> list[Point]:
        """目标区域边界上通往其他区域的门中点(用于跨房间时终点贴近门)。"""

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

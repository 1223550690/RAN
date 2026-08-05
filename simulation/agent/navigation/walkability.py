"""可行走性判定与碰撞检测。

障碍来源:
- 全局墙体(场景级 walls + area 级 walls 转全局)。
- 室内区域边界(space == "indoor" 的区域四条边界按外墙处理)。
- 阻挡元素(blocks_movement=True,矩形)。

所有几何都以 Agent 半径膨胀处理;判定统一走 point_clear / segment_clear。
"""

from __future__ import annotations

import math

from .geometry import (
    Point,
    Rect,
    _aabbs_overlap,
    _expand_interval,
    _interpolate_segment,
    _point_in_expanded_aabb,
    _projection_interval,
    _segment_aabb,
    _subtract_intervals,
    point_in_rect,
    point_to_segment_distance,
    segment_intersection,
    segments_collinear_overlap,
)
from .semantic_index import SceneSemanticIndex


class WalkabilityMap:
    def __init__(self, semantic_index: SceneSemanticIndex, *, agent_radius: float = 0.3) -> None:
        self.index = semantic_index
        self.agent_radius = max(0.05, float(agent_radius))
        self.walls: list[tuple[Point, Point]] = []
        self.obstacles: list[Rect] = []
        # 空间预筛:每堵墙/障碍的 AABB,碰撞检测先剔除不相交项,避免大场景全量遍历。
        self._wall_aabbs: list[Rect] = []
        self._obstacle_aabbs: list[Rect] = []
        self._build()

    def _build(self) -> None:
        for wall in self.index.walls:
            if wall.blocks_movement:
                self.walls.extend(self._segment_minus_openings(wall.segment))
        self._build_boundary_walls()
        for element in self.index.elements.values():
            if not element.blocks_movement:
                continue
            half_w, half_h = element.size[0] / 2, element.size[1] / 2
            self.obstacles.append(
                (
                    element.center[0] - half_w,
                    element.center[1] - half_h,
                    element.center[0] + half_w,
                    element.center[1] + half_h,
                )
            )
        self._wall_aabbs = [_segment_aabb(segment) for segment in self.walls]
        self._obstacle_aabbs = list(self.obstacles)

    def _openings_on(self, segment: tuple[Point, Point]) -> list[tuple[float, float]]:
        """返回与线段共线重叠的 open 门开口区间(参数化 [0,1])。

        门 = 可通行开口:任何墙(显式或边界)在门开口处让路。
        """

        openings: list[tuple[float, float]] = []
        for portal in self.index.portals.values():
            if not portal.open:
                continue
            if segments_collinear_overlap(
                segment[0], segment[1], portal.segment[0], portal.segment[1], eps=0.1
            ):
                openings.append(_projection_interval(segment, portal.segment))
        return openings

    def _segment_minus_openings(self, segment: tuple[Point, Point]) -> list[tuple[Point, Point]]:
        """墙段扣除门开口(两端按 agent 半径扩张)后的剩余子段。"""

        keep = [(0.0, 1.0)]
        for interval in self._openings_on(segment):
            keep = _subtract_intervals(
                keep, _expand_interval(interval, self.agent_radius, segment)
            )
        result: list[tuple[Point, Point]] = []
        for t_start, t_end in keep:
            if t_end - t_start < 0.005:  # 过滤数值噪声产生的零长度墙段。
                continue
            result.append(_interpolate_segment(segment, t_start, t_end))
        return result

    def _build_boundary_walls(self) -> None:
        """室内区域边界墙,处理共享边界与门开口。

        - 相邻区域共享边界(共线重叠):整段不建墙(通道语义,相邻建筑连通)。
        - 非共享边界:扣除门(portal)开口区间(两端按 agent 半径扩张)后建墙。
        """

        indoor_segments: list[tuple[tuple[Point, Point], str]] = []
        for area in self.index.areas.values():
            if area.metadata.get("space") != "indoor":
                continue
            min_x, min_y, max_x, max_y = area.bounds
            for segment in (
                ((min_x, min_y), (max_x, min_y)),
                ((max_x, min_y), (max_x, max_y)),
                ((max_x, max_y), (min_x, max_y)),
                ((min_x, max_y), (min_x, min_y)),
            ):
                indoor_segments.append((segment, area.area_id))

        for segment, area_id in indoor_segments:
            # 1) 与其他区域共享的边界区间(整段无墙)。
            shared: list[tuple[float, float]] = []
            for other_segment, other_id in indoor_segments:
                if other_id == area_id:
                    continue
                if segments_collinear_overlap(
                    segment[0], segment[1], other_segment[0], other_segment[1], eps=0.1
                ):
                    shared.append(_projection_interval(segment, other_segment))
            # 2) 边界上的门开口区间(两端按 agent 半径扩张)。
            openings: list[tuple[float, float]] = []
            for portal in self.index.portals.values():
                if not portal.open:
                    continue
                if segments_collinear_overlap(
                    segment[0], segment[1], portal.segment[0], portal.segment[1], eps=0.1
                ):
                    openings.append(_projection_interval(segment, portal.segment))
            # 3) 保留区间 = 整段 - 共享区间 - 门开口。
            keep = [(0.0, 1.0)]
            for interval in shared:
                keep = _subtract_intervals(keep, interval)
            for interval in openings:
                keep = _subtract_intervals(
                    keep, _expand_interval(interval, self.agent_radius, segment)
                )
            for t_start, t_end in keep:
                if t_end - t_start < 0.005:  # 过滤数值噪声产生的零长度墙段。
                    continue
                self.walls.append(_interpolate_segment(segment, t_start, t_end))

    # ------------------------------------------------------------------ 点判定

    def point_clear(self, point: Point) -> bool:
        """点是否可站立(与所有墙/障碍保持至少 agent_radius 距离)。"""

        radius = self.agent_radius
        for aabb, (start, end) in zip(self._wall_aabbs, self.walls):
            if not _point_in_expanded_aabb(point, aabb, radius):
                continue
            if point_to_segment_distance(point, start, end) < radius - 1e-9:
                return False
        for rect in self.obstacles:
            if not _point_in_expanded_aabb(point, rect, radius):
                continue
            if point_to_rect_distance(point, rect) < radius - 1e-9:
                return False
        return True

    def point_to_nearest_obstacle(self, point: Point) -> float:
        """点到最近障碍(墙或矩形)的距离;被阻挡时为 0。"""

        best = float("inf")
        for aabb, (start, end) in zip(self._wall_aabbs, self.walls):
            if best < float("inf") and not _point_in_expanded_aabb(point, aabb, best):
                continue
            best = min(best, point_to_segment_distance(point, start, end))
        for rect in self.obstacles:
            if best < float("inf") and not _point_in_expanded_aabb(point, rect, best):
                continue
            best = min(best, point_to_rect_distance(point, rect))
        return best

    # ------------------------------------------------------------------ 线段判定

    def segment_clear(self, a: Point, b: Point) -> bool:
        """线段 ab 是否可通行(与所有膨胀障碍保持至少 agent_radius 距离)。"""

        radius = self.agent_radius
        seg_aabb = _segment_aabb((a, b))
        for aabb, (start, end) in zip(self._wall_aabbs, self.walls):
            if not _aabbs_overlap(seg_aabb, aabb):
                continue
            if segment_to_segment_distance(a, b, start, end) < radius - 1e-9:
                return False
        for rect in self.obstacles:
            if not _aabbs_overlap(seg_aabb, rect):
                continue
            if segment_to_rect_distance(a, b, rect) < radius - 1e-9:
                return False
        return True

    def segment_blocked_by_wall(self, a: Point, b: Point) -> bool:
        """线段 ab 是否与任意墙体线段相交(不含膨胀,用于视线简化)。"""

        seg_aabb = _segment_aabb((a, b))
        for aabb, (start, end) in zip(self._wall_aabbs, self.walls):
            if not _aabbs_overlap(seg_aabb, aabb):
                continue
            if segment_intersection(a, b, start, end) is not None:
                return True
        return False

    # ------------------------------------------------------------------ 起点修正

    def find_safe_start(self, point: Point, *, max_radius: float | None = None) -> Point | None:
        """起点不可站立时,在螺旋网格上搜索最近安全点。"""

        if self.point_clear(point):
            return point
        step = max(self.agent_radius, 0.25)
        max_radius = max_radius if max_radius is not None else step * 20
        rings = int(max_radius / step) + 1
        for ring in range(1, rings + 1):
            radius = ring * step
            samples = max(8, int(2 * math.pi * radius / step))
            for i in range(samples):
                angle = 2 * math.pi * i / samples
                candidate = (point[0] + radius * math.cos(angle), point[1] + radius * math.sin(angle))
                if self.point_clear(candidate):
                    return candidate
        return None


# ------------------------------------------------------------------ 距离工具


def point_to_rect_distance(point: Point, rect: Rect) -> float:
    """点到矩形的最短距离;点在矩形内时为 0。"""

    min_x, min_y, max_x, max_y = rect
    x, y = point
    if point_in_rect(point, rect):
        return 0.0
    dx = max(min_x - x, 0.0, x - max_x)
    dy = max(min_y - y, 0.0, y - max_y)
    return (dx * dx + dy * dy) ** 0.5


def segment_to_segment_distance(a: Point, b: Point, c: Point, d: Point) -> float:
    """两线段间最短距离;相交时为 0。"""

    if segment_intersection(a, b, c, d) is not None:
        return 0.0
    return min(
        point_to_segment_distance(a, c, d),
        point_to_segment_distance(b, c, d),
        point_to_segment_distance(c, a, b),
        point_to_segment_distance(d, a, b),
    )


def segment_to_rect_distance(a: Point, b: Point, rect: Rect) -> float:
    """线段到矩形的最短距离;相交或线段端点在矩形内时为 0。"""

    if point_in_rect(a, rect) or point_in_rect(b, rect):
        return 0.0
    min_x, min_y, max_x, max_y = rect
    corners = [
        (min_x, min_y),
        (max_x, min_y),
        (max_x, max_y),
        (min_x, max_y),
    ]
    best = min(
        point_to_rect_distance(a, rect),
        point_to_rect_distance(b, rect),
    )
    for i in range(4):
        best = min(best, segment_to_segment_distance(a, b, corners[i], corners[(i + 1) % 4]))
    return best

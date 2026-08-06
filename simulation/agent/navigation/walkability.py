"""Walkability checks and collision detection.

Obstacle sources:
- Global walls (scene-level walls + area-level walls converted to global coordinates).
- Indoor area boundaries (the four boundary edges of areas with space == "indoor" are treated as exterior walls).
- Blocking elements (blocks_movement=True, rectangles).

All geometry is inflated by the agent radius; checks go through point_clear / segment_clear uniformly.
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
    closest_point_on_segment,
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
        # Spatial pre-filter: AABB per wall/obstacle; collision checks cull non-intersecting items first, avoiding full traversal on large scenes.
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
        """Return parameterized [0,1] intervals of open-door openings collinear-overlapping the segment.

        Door = passable opening: any wall (explicit or boundary) yields at a door opening.
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
        """Remaining sub-segments of a wall segment after subtracting door openings (both ends expanded by the agent radius)."""

        keep = [(0.0, 1.0)]
        for interval in self._openings_on(segment):
            keep = _subtract_intervals(
                keep, _expand_interval(interval, self.agent_radius, segment)
            )
        result: list[tuple[Point, Point]] = []
        for t_start, t_end in keep:
            if t_end - t_start < 0.005:  # filter zero-length wall segments caused by numeric noise.
                continue
            result.append(_interpolate_segment(segment, t_start, t_end))
        return result

    def _build_boundary_walls(self) -> None:
        """Boundary walls of indoor areas, handling shared boundaries and door openings.

        - Shared boundary with an adjacent area (collinear overlap): no wall for the whole segment (channel semantics; adjacent buildings connect).
        - Non-shared boundary: build walls after subtracting door (portal) opening intervals (both ends expanded by the agent radius).
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
            # 1) Boundary intervals shared with other areas (no wall for the whole segment).
            shared: list[tuple[float, float]] = []
            for other_segment, other_id in indoor_segments:
                if other_id == area_id:
                    continue
                if segments_collinear_overlap(
                    segment[0], segment[1], other_segment[0], other_segment[1], eps=0.1
                ):
                    shared.append(_projection_interval(segment, other_segment))
            # 2) Door opening intervals on the boundary (both ends expanded by the agent radius).
            openings: list[tuple[float, float]] = []
            for portal in self.index.portals.values():
                if not portal.open:
                    continue
                if segments_collinear_overlap(
                    segment[0], segment[1], portal.segment[0], portal.segment[1], eps=0.1
                ):
                    openings.append(_projection_interval(segment, portal.segment))
            # 3) Kept intervals = whole segment - shared intervals - door openings.
            keep = [(0.0, 1.0)]
            for interval in shared:
                keep = _subtract_intervals(keep, interval)
            for interval in openings:
                keep = _subtract_intervals(
                    keep, _expand_interval(interval, self.agent_radius, segment)
                )
            for t_start, t_end in keep:
                if t_end - t_start < 0.005:  # filter zero-length wall segments caused by numeric noise.
                    continue
                self.walls.append(_interpolate_segment(segment, t_start, t_end))

    # ------------------------------------------------------------------ point checks

    def point_clear(self, point: Point) -> bool:
        """Whether a point is standable (at least agent_radius away from all walls/obstacles)."""

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
        """Distance from a point to the nearest obstacle (wall or rectangle); 0 when blocked."""

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

    # ------------------------------------------------------------------ segment checks

    def segment_clear(self, a: Point, b: Point) -> bool:
        """Whether segment ab is passable (at least agent_radius away from all inflated obstacles)."""

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
        """Whether segment ab intersects any wall segment (no inflation; used for line-of-sight simplification)."""

        seg_aabb = _segment_aabb((a, b))
        for aabb, (start, end) in zip(self._wall_aabbs, self.walls):
            if not _aabbs_overlap(seg_aabb, aabb):
                continue
            if segment_intersection(a, b, start, end) is not None:
                return True
        return False

    # ------------------------------------------------------------------ start adjustment

    def find_safe_start(self, point: Point, *, max_radius: float | None = None) -> Point | None:
        """When the start point is not standable, search for the nearest safe point on a spiral grid."""

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

    # ------------------------------------------------------------------ push-away helpers

    def clearance_and_direction(self, point: Point) -> tuple[float, tuple[float, float]]:
        """Return the distance from point to the nearest wall/obstacle and the unit direction "away from the nearest wall".

        When the distance is 0, the direction defaults to the fixed axis (1, 0).
        """

        best_distance = float("inf")
        best_direction = (1.0, 0.0)
        for wall, aabb in zip(self.walls, self._wall_aabbs):
            if not _point_in_expanded_aabb(point, aabb, best_distance):
                continue
            closest = closest_point_on_segment(point, wall[0], wall[1])
            dx, dy = point[0] - closest[0], point[1] - closest[1]
            distance = (dx * dx + dy * dy) ** 0.5
            if distance < best_distance:
                best_distance = distance
                if distance > 1e-9:
                    best_direction = (dx / distance, dy / distance)
        for rect in self._obstacle_aabbs:
            distance = point_to_rect_distance(point, rect)
            if distance < best_distance:
                best_distance = distance
                if distance > 1e-9:
                    dx = max(rect[0] - point[0], 0.0) + min(rect[2] - point[0], 0.0)
                    dy = max(rect[1] - point[1], 0.0) + min(rect[3] - point[1], 0.0)
                    norm = (dx * dx + dy * dy) ** 0.5
                    if norm > 1e-9:
                        best_direction = (dx / norm, dy / norm)
        return best_distance, best_direction


# ------------------------------------------------------------------ distance utilities


def point_to_rect_distance(point: Point, rect: Rect) -> float:
    """Shortest distance from a point to a rectangle; 0 when the point is inside."""

    min_x, min_y, max_x, max_y = rect
    x, y = point
    if point_in_rect(point, rect):
        return 0.0
    dx = max(min_x - x, 0.0, x - max_x)
    dy = max(min_y - y, 0.0, y - max_y)
    return (dx * dx + dy * dy) ** 0.5


def segment_to_segment_distance(a: Point, b: Point, c: Point, d: Point) -> float:
    """Shortest distance between two segments; 0 when they intersect."""

    if segment_intersection(a, b, c, d) is not None:
        return 0.0
    return min(
        point_to_segment_distance(a, c, d),
        point_to_segment_distance(b, c, d),
        point_to_segment_distance(c, a, b),
        point_to_segment_distance(d, a, b),
    )


def segment_to_rect_distance(a: Point, b: Point, rect: Rect) -> float:
    """Shortest distance from a segment to a rectangle; 0 when they intersect or an endpoint is inside."""

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

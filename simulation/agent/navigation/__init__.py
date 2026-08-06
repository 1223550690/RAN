"""NavigationPlanner: navigation facade combining semantic resolution, room graph, endpoint sampling, A*, smoothing, and scoring.

Pipeline (aligned with the 3D scene navigation logic):
1. Resolve the destination by full hierarchical path/name/alias.
2. Determine which area the start and the destination are in.
3. When crossing rooms, build an area-door connection graph and derive the door sequence via BFS.
4. If the start falls inside an obstacle, search for a nearby safe start.
5. Sample up to max_candidates candidate endpoints around the target area/element.
6. Run 8-direction A* for each candidate (segmented through the door sequence).
7. Use continuous segment collision checks to prevent wall-cutting after simplification, then line-of-sight simplification and minimum-spacing filtering.
8. Score the candidate routes and pick the result.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .astar import GridAstar
from .endpoint_sampler import EndpointSampler
from .geometry import Point, Rect
from .path_smoothing import push_away_from_walls, smooth_path
from .room_graph import RoomGraph
from .route_scorer import RouteScore, score_route
from .semantic_index import ResolvedDestination, SceneSemanticIndex
from .walkability import WalkabilityMap


@dataclass(frozen=True, slots=True)
class PathPlan:
    waypoints: tuple[Point, ...]  # waypoints: smoothed world-coordinate path (including start and end).
    destination: ResolvedDestination  # destination: resolved target.
    endpoint: Point  # endpoint: selected endpoint.
    doors: tuple  # doors: cross-room door sequence (IndexedPortal tuple).
    score: RouteScore  # score: scoring details of the selected route.


@dataclass(slots=True)
class PathPlanResult:
    plan: PathPlan | None  # plan: path plan on success, None on failure.
    error: str | None = None  # error: failure reason.

    @property
    def ok(self) -> bool:
        return self.plan is not None


class NavigationPlanner:
    def __init__(
        self,
        scene,
        *,
        aliases: dict[str, str] | None = None,
        agent_radius: float = 0.5,
        seed: int = 42,
        cell_size: float = 0.25,
        max_candidates: int = 48,
        max_astar_candidates: int = 12,
    ) -> None:
        self.semantic_index = SceneSemanticIndex(scene, aliases=aliases)
        self.walkability = WalkabilityMap(self.semantic_index, agent_radius=agent_radius)
        self.room_graph = RoomGraph(self.semantic_index)
        self.endpoint_sampler = EndpointSampler(
            self.walkability, max_candidates=max_candidates, seed=seed
        )
        self.agent_radius = agent_radius
        self.clearance_margin = agent_radius + 0.3  # push-away margin (radius + visual margin)
        self.cell_size = cell_size
        self.max_astar_candidates = max_astar_candidates
        self._astar: GridAstar | None = None
        self._coarse: GridAstar | None = None
        self._local_astars: dict[str, GridAstar] = {}

    # ------------------------------------------------------------------ public interface

    def resolve_destination(self, ref: str) -> ResolvedDestination | None:
        """Resolve a semantic destination; returns None when resolution fails."""

        return self.semantic_index.resolve(ref)

    def current_room(self, point: Point) -> str | None:
        """Return the deepest area ID containing the point; None when outdoors."""

        area = self.semantic_index.find_area_at(point)
        return area.area_id if area is not None else None

    def plan_path(self, start: Point, destination_ref: str) -> PathPlanResult:
        """Plan a complete path from the start point to the semantic destination."""

        destination = self.semantic_index.resolve(destination_ref)
        if destination is None:
            return PathPlanResult(None, error=f"destination_ref unresolved: {destination_ref!r}")

        safe_start = self.walkability.find_safe_start(start)
        if safe_start is None:
            return PathPlanResult(None, error=f"no safe start position near {start!r}")

        doors = self._door_sequence(safe_start, destination)
        candidates = self.endpoint_sampler.sample(destination)
        if not candidates:
            return PathPlanResult(None, error=f"no walkable endpoint for destination {destination_ref!r}")

        # Trunk path: start -> each door (shared by all candidates; computed once).
        trunk, trunk_end = self._build_trunk(safe_start, doors)
        if trunk is None:
            return PathPlanResult(None, error=f"no route to door sequence for destination {destination_ref!r}")
        # Shared tail segment: last door -> target area center (all candidate endpoints are inside the target area; share this segment).
        tail, tail_end = self._build_tail(trunk_end, destination.position)

        best: PathPlan | None = None
        straight_distance = ((safe_start[0] - destination.position[0]) ** 2 + (safe_start[1] - destination.position[1]) ** 2) ** 0.5
        # Sort candidates by distance to the tail segment end; evaluate nearer ones first.
        ordered = sorted(
            candidates,
            key=lambda point: (point[0] - tail_end[0]) ** 2 + (point[1] - tail_end[1]) ** 2,
        )
        for index, endpoint in enumerate(ordered):
            if index >= self.max_astar_candidates:
                break
            waypoints = self._build_candidate_path(trunk, tail, tail_end, endpoint)
            if waypoints is None:
                continue
            smoothed = smooth_path(waypoints, self.walkability)
            if len(smoothed) < 2:
                continue
            smoothed = push_away_from_walls(smoothed, self.walkability, target_clearance=self.clearance_margin)
            score = score_route(smoothed, self.walkability, destination)
            plan = PathPlan(
                waypoints=tuple(smoothed),
                destination=destination,
                endpoint=endpoint,
                doors=tuple(doors),
                score=score,
            )
            if best is None or score.score < best.score.score:
                best = plan
            # Early termination: a straight-line-reachable or near-straight route was found.
            if score.score <= straight_distance * 1.3 + 2.0:
                break
        if best is None:
            return PathPlanResult(None, error=f"no route found to destination {destination_ref!r}")
        return PathPlanResult(best)

    # ------------------------------------------------------------------ internals

    def _get_astar(self) -> GridAstar:
        """Global fine grid: kept as a fallback for scenarios needing full-scene detail (cross-building segments now use the coarse grid)."""

        if self._astar is None:
            self._astar = GridAstar(
                self.walkability,
                bounds=self.semantic_index.scene_bounds(),
                cell_size=self.cell_size,
            )
        return self._astar

    def _coarse_astar(self) -> GridAstar:
        """Global coarse grid: used for cross-building/outdoor segments; large cells, few grid nodes, fast detour planning."""

        if self._coarse is None:
            self._coarse = GridAstar(
                self.walkability,
                bounds=self.semantic_index.scene_bounds(),
                cell_size=self.cell_size,
                max_cells=400,
            )
        return self._coarse

    def _top_level_area_id(self, point: Point) -> str | None:
        """Return the top-level area ID (building level) containing the point; None when outdoors."""

        area = self.semantic_index.find_area_at(point)
        while area is not None and area.parent_id is not None:
            parent = self.semantic_index.get_area(area.parent_id)
            if parent is None:
                break
            area = parent
        return area.area_id if area is not None else None

    def _local_astar(self, top_area_id: str) -> GridAstar:
        """Building-level local grid: finer cells covering only one building; fast and precise planning."""

        cached = self._local_astars.get(top_area_id)
        if cached is not None:
            return cached
        area = self.semantic_index.get_area(top_area_id)
        min_x, min_y, max_x, max_y = area.bounds
        margin = max(2.0, (max_x - min_x) * 0.05, (max_y - min_y) * 0.05)
        bounds = (min_x - margin, min_y - margin, max_x + margin, max_y + margin)
        cached = GridAstar(
            self.walkability,
            bounds=bounds,
            cell_size=self.cell_size,
            max_cells=600,
        )
        self._local_astars[top_area_id] = cached
        return cached

    def _segment_astar(self, a: Point, b: Point) -> GridAstar:
        """Pick the grid for segment planning: both ends in the same building -> local grid; cross-building/outdoor -> coarse grid."""

        top_a = self._top_level_area_id(a)
        top_b = self._top_level_area_id(b)
        if top_a is not None and top_a == top_b:
            return self._local_astar(top_a)
        return self._coarse_astar()

    def _door_sequence(self, start: Point, destination: ResolvedDestination) -> list:
        start_area = self.semantic_index.find_area_at(start)
        start_area_id = (
            start_area.area_id if start_area is not None else RoomGraph.OUTSIDE
        )
        doors = self.room_graph.find_door_sequence(start_area_id, destination.area_id)
        return doors or []

    def _build_trunk(
        self,
        start: Point,
        doors: list,
    ) -> tuple[list[Point] | None, Point]:
        """Compute the trunk path shared by all candidates: start -> each door midpoint (picking local/global grid per segment)."""

        waypoints: list[Point] = [start]
        current = start
        for door in doors:
            door_point = self.walkability.find_safe_start(door.center)
            if door_point is None:
                return None, current
            if not self.walkability.segment_clear(current, door_point):
                segment = self._segment_astar(current, door_point).find_path(current, door_point)
                if segment is None:
                    return None, current
                waypoints.extend(segment[1:])
            else:
                waypoints.append(door_point)
            current = door_point
        return waypoints, current

    def _build_tail(
        self,
        trunk_end: Point,
        goal_position: Point,
    ) -> tuple[list[Point], Point]:
        """Shared tail segment: trunk end -> target area center. Returns (path, end point)."""

        tail_start = trunk_end
        tail_end = self.walkability.find_safe_start(goal_position)
        if tail_end is None:
            return [tail_start], tail_start
        if self.walkability.segment_clear(tail_start, tail_end):
            return [tail_start, tail_end], tail_end
        segment = self._segment_astar(tail_start, tail_end).find_path(tail_start, tail_end)
        if segment is None:
            return [tail_start], tail_start
        return segment, segment[-1]

    def _build_candidate_path(
        self,
        trunk: list[Point],
        tail: list[Point],
        tail_end: Point,
        endpoint: Point,
    ) -> list[Point] | None:
        """Build a candidate path: shared trunk + shared tail + short segment from the tail end to the candidate endpoint."""

        prefix = trunk + tail[1:]
        if self.walkability.segment_clear(tail_end, endpoint):
            return prefix + [endpoint]
        segment = self._segment_astar(tail_end, endpoint).find_path(tail_end, endpoint)
        if segment is None:
            return None
        return prefix + segment[1:]

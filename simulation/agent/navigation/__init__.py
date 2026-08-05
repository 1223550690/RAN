"""NavigationPlanner:导航门面,组合语义解析、房间图、终点采样、A*、平滑与评分。

流程(与 3D 场景导航逻辑对齐):
1. 按完整层级路径/名字/别名解析目标。
2. 判断起点与目标分别位于哪个区域。
3. 跨房间时构建区域-门连接图,通过 BFS 确定门序列。
4. 起点落在障碍中时,搜索附近安全起点。
5. 在目标区域/元素各侧采样最多 max_candidates 个候选终点。
6. 对每个候选执行八方向 A*(分段经过门序列)。
7. 用连续线段碰撞检查防止简化后穿墙,再做视线简化与最小间距过滤。
8. 对候选路线评分并选择结果。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .astar import GridAstar
from .endpoint_sampler import EndpointSampler
from .geometry import Point, Rect
from .path_smoothing import smooth_path
from .room_graph import RoomGraph
from .route_scorer import RouteScore, score_route
from .semantic_index import ResolvedDestination, SceneSemanticIndex
from .walkability import WalkabilityMap


@dataclass(frozen=True, slots=True)
class PathPlan:
    waypoints: tuple[Point, ...]  # waypoints: 平滑后的世界坐标路径(含起点与终点)。
    destination: ResolvedDestination  # destination: 解析后的目标。
    endpoint: Point  # endpoint: 选定的终点。
    doors: tuple  # doors: 跨房间门序列(IndexedPortal 元组)。
    score: RouteScore  # score: 选中路线的评分明细。


@dataclass(slots=True)
class PathPlanResult:
    plan: PathPlan | None  # plan: 成功时为路径计划,失败为 None。
    error: str | None = None  # error: 失败原因。

    @property
    def ok(self) -> bool:
        return self.plan is not None


class NavigationPlanner:
    def __init__(
        self,
        scene,
        *,
        aliases: dict[str, str] | None = None,
        agent_radius: float = 0.3,
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
        self.cell_size = cell_size
        self.max_astar_candidates = max_astar_candidates
        self._astar: GridAstar | None = None
        self._coarse: GridAstar | None = None
        self._local_astars: dict[str, GridAstar] = {}

    # ------------------------------------------------------------------ 对外接口

    def resolve_destination(self, ref: str) -> ResolvedDestination | None:
        """语义目标解析;解析失败返回 None。"""

        return self.semantic_index.resolve(ref)

    def current_room(self, point: Point) -> str | None:
        """返回点所在的最深层区域 ID;户外为 None。"""

        area = self.semantic_index.find_area_at(point)
        return area.area_id if area is not None else None

    def plan_path(self, start: Point, destination_ref: str) -> PathPlanResult:
        """规划从起点到语义目标的完整路径。"""

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

        # 主干路径:起点 → 各门(所有候选共享,只算一次)。
        trunk, trunk_end = self._build_trunk(safe_start, doors)
        if trunk is None:
            return PathPlanResult(None, error=f"no route to door sequence for destination {destination_ref!r}")
        # 共享末端段:最后门 → 目标区域中心(候选终点都在目标区域内,共享此段)。
        tail, tail_end = self._build_tail(trunk_end, destination.position)

        best: PathPlan | None = None
        straight_distance = ((safe_start[0] - destination.position[0]) ** 2 + (safe_start[1] - destination.position[1]) ** 2) ** 0.5
        # 候选按到共享末端段终点的距离排序,优先评估近的。
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
            # 提前终止:已找到直线可达或足够接近直线的路线。
            if score.score <= straight_distance * 1.3 + 2.0:
                break
        if best is None:
            return PathPlanResult(None, error=f"no route found to destination {destination_ref!r}")
        return PathPlanResult(best)

    # ------------------------------------------------------------------ 内部

    def _get_astar(self) -> GridAstar:
        """全局细网格:保留给需要全场景细节的兜底场景(当前跨建筑段已改用粗网格)。"""

        if self._astar is None:
            self._astar = GridAstar(
                self.walkability,
                bounds=self.semantic_index.scene_bounds(),
                cell_size=self.cell_size,
            )
        return self._astar

    def _coarse_astar(self) -> GridAstar:
        """全局粗网格:跨建筑/户外段使用,cell 大、格数少,绕行规划快。"""

        if self._coarse is None:
            self._coarse = GridAstar(
                self.walkability,
                bounds=self.semantic_index.scene_bounds(),
                cell_size=self.cell_size,
                max_cells=400,
            )
        return self._coarse

    def _top_level_area_id(self, point: Point) -> str | None:
        """返回点所在的最顶层区域 ID(建筑级);户外为 None。"""

        area = self.semantic_index.find_area_at(point)
        while area is not None and area.parent_id is not None:
            parent = self.semantic_index.get_area(area.parent_id)
            if parent is None:
                break
            area = parent
        return area.area_id if area is not None else None

    def _local_astar(self, top_area_id: str) -> GridAstar:
        """建筑级局部网格:更细的 cell,只覆盖单建筑范围,规划快且精确。"""

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
        """选择段规划使用的网格:段两端同建筑 → 局部网格;跨建筑/户外 → 粗网格。"""

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
        """计算所有候选共享的主干路径:起点 → 各门中点(逐段选择局部/全局网格)。"""

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
        """共享末端段:主干末端 → 目标区域中心。返回 (路径, 末端点)。"""

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
        """构造候选路径:共享主干 + 共享末端段 + 末端点到候选终点的短段。"""

        prefix = trunk + tail[1:]
        if self.walkability.segment_clear(tail_end, endpoint):
            return prefix + [endpoint]
        segment = self._segment_astar(tail_end, endpoint).find_path(tail_end, endpoint)
        if segment is None:
            return None
        return prefix + segment[1:]

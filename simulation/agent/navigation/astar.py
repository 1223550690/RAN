"""八方向网格 A*。

- 代价 = 行走距离 + 靠近障碍物的净空惩罚(以可行邻居数近似净空)。
- 禁止斜向穿过两个相邻障碍的夹角:斜向移动要求两个正交邻居均可通行。
- 平局规则确定:按 (f, h, 入队序号) 排序,保证同输入同输出(可复现)。
"""

from __future__ import annotations

import heapq
from array import array
from collections import deque

from .geometry import Point, Rect, point_to_segment_distance
from .walkability import WalkabilityMap, point_to_rect_distance

_STRAIGHT = 1.0
_DIAGONAL = 2 ** 0.5

# 八方向:0-3 正交,4-7 对角。
_DIRECTIONS = (
    (1, 0),
    (-1, 0),
    (0, 1),
    (0, -1),
    (1, 1),
    (1, -1),
    (-1, 1),
    (-1, -1),
)


class GridAstar:
    def __init__(
        self,
        walkability: WalkabilityMap,
        *,
        bounds: Rect,
        cell_size: float = 0.25,
        max_cells: int = 2000,
        clearance_penalty: float = 0.35,
    ) -> None:
        self.walkability = walkability
        min_x, min_y, max_x, max_y = bounds
        diagonal = ((max_x - min_x) ** 2 + (max_y - min_y) ** 2) ** 0.5
        self.cell_size = max(cell_size, diagonal / max_cells)
        self.min_x, self.min_y = min_x, min_y
        self.cols = max(2, int((max_x - min_x) / self.cell_size) + 1)
        self.rows = max(2, int((max_y - min_y) / self.cell_size) + 1)
        self.clearance_penalty = clearance_penalty
        self._blocked_cache: dict[tuple[int, int], bool] = {}
        # 网格空间索引:cell -> 墙/障碍索引。点判定只查所在 cell 的障碍,
        # 避免大场景全量遍历(常数从数百条降到个位数)。
        self._cell_walls: dict[int, list[int]] = {}
        self._cell_obstacles: dict[int, list[int]] = {}
        self._index_obstacles()
        # 连通性预检:从起点 flood fill 标记可达格,目标不可达时立即失败,
        # 避免 A* 无解时探索整个网格。
        self._reachable_from: tuple[int, int] | None = None
        self._reachable: array | None = None

    # ------------------------------------------------------------------ 空间索引

    def _index_obstacles(self) -> None:
        for index, (start, end) in enumerate(self.walkability.walls):
            for cell in self._rasterize(start, end):
                self._cell_walls.setdefault(cell, []).append(index)
        for index, rect in enumerate(self.walkability.obstacles):
            min_x, min_y, max_x, max_y = rect
            top_left = self.to_cell((min_x, min_y))
            bottom_right = self.to_cell((max_x, max_y))
            for col in range(top_left[0], bottom_right[0] + 1):
                for row in range(top_left[1], bottom_right[1] + 1):
                    self._cell_obstacles.setdefault(col + row * self.cols, []).append(index)

    def _rasterize(self, start: Point, end: Point) -> set[int]:
        """把墙线段光栅化到经过的网格 cell(按 cell_size/2 步进)。"""

        cells: set[int] = set()
        length = ((end[0] - start[0]) ** 2 + (end[1] - start[1]) ** 2) ** 0.5
        steps = max(2, int(length / (self.cell_size / 2)) + 1)
        for i in range(steps + 1):
            ratio = i / steps
            point = (
                start[0] + (end[0] - start[0]) * ratio,
                start[1] + (end[1] - start[1]) * ratio,
            )
            col, row = self.to_cell(point)
            cells.add(col + row * self.cols)
        return cells

    def _point_clear_fast(self, point: Point, cell: tuple[int, int]) -> bool:
        """只查所在 cell 附近 cell 的障碍(覆盖 agent 半径范围)。"""

        col, row = cell
        radius = self.walkability.agent_radius
        span = max(1, int(radius / self.cell_size) + 1)  # 膨胀半径覆盖的格数。
        for dcol in range(-span, span + 1):
            for drow in range(-span, span + 1):
                ncol, nrow = col + dcol, row + drow
                if not (0 <= ncol < self.cols and 0 <= nrow < self.rows):
                    continue
                neighbor = ncol + nrow * self.cols
                for wall_index in self._cell_walls.get(neighbor, ()):
                    start, end = self.walkability.walls[wall_index]
                    if point_to_segment_distance(point, start, end) < radius - 1e-9:
                        return False
                for obstacle_index in self._cell_obstacles.get(neighbor, ()):
                    rect = self.walkability.obstacles[obstacle_index]
                    if point_to_rect_distance(point, rect) < radius - 1e-9:
                        return False
        return True

    # ------------------------------------------------------------------ 网格坐标

    def to_cell(self, point: tuple[float, float]) -> tuple[int, int]:
        col = int((point[0] - self.min_x) / self.cell_size)
        row = int((point[1] - self.min_y) / self.cell_size)
        return max(0, min(self.cols - 1, col)), max(0, min(self.rows - 1, row))

    def to_point(self, cell: tuple[int, int]) -> tuple[float, float]:
        col, row = cell
        return (
            self.min_x + (col + 0.5) * self.cell_size,
            self.min_y + (row + 0.5) * self.cell_size,
        )

    def _is_blocked(self, cell: tuple[int, int]) -> bool:
        cached = self._blocked_cache.get(cell)
        if cached is None:
            cached = not self._point_clear_fast(self.to_point(cell), cell)
            self._blocked_cache[cell] = cached
        return cached

    # ------------------------------------------------------------------ 连通性预检

    def _ensure_reachable(self, start_cell: tuple[int, int]) -> None:
        """从起点 flood fill 标记可达格;目标不可达时 find_path 立即失败。"""

        if self._reachable_from == start_cell:
            return
        visited = array("b", [0]) * (self.cols * self.rows)
        stack: deque[tuple[int, int]] = deque([start_cell])
        visited[start_cell[1] * self.cols + start_cell[0]] = 1
        while stack:
            col, row = stack.pop()
            for dx, dy in _DIRECTIONS:
                ncol, nrow = col + dx, row + dy
                if not (0 <= ncol < self.cols and 0 <= nrow < self.rows):
                    continue
                if visited[nrow * self.cols + ncol]:
                    continue
                if self._is_blocked((ncol, nrow)):
                    continue
                visited[nrow * self.cols + ncol] = 1
                stack.append((ncol, nrow))
        self._reachable_from = start_cell
        self._reachable = visited

    def _is_reachable(self, cell: tuple[int, int]) -> bool:
        if self._reachable is None:
            return True
        return bool(self._reachable[cell[1] * self.cols + cell[0]])

    # ------------------------------------------------------------------ A*

    def find_path(
        self,
        start: tuple[float, float],
        goal: tuple[float, float],
    ) -> list[tuple[float, float]] | None:
        """返回从起点到目标点的世界坐标路径;无解返回 None。

        目标格松弛:目标点所在格子中心不可行(常见于门/边界线上的点)时,
        在其邻域搜索最近可行格作为终点;路径末端再尝试替换回实际目标点。
        """

        start_cell = self.to_cell(start)
        goal_cell = self.to_cell(goal)
        self._ensure_reachable(start_cell)
        if not self._is_reachable(goal_cell):
            return None
        if self._is_blocked(goal_cell):
            relaxed = self._relax_goal(goal_cell)
            if relaxed is None:
                return None
            goal_cell = relaxed

        def heuristic(cell: tuple[int, int]) -> float:
            # octile 距离:八方向移动的精确下界,比曼哈顿更紧,扩展格数更少。
            dx = abs(cell[0] - goal_cell[0])
            dy = abs(cell[1] - goal_cell[1])
            return max(dx, dy) + (_DIAGONAL - 1.0) * min(dx, dy)

        open_heap: list[tuple[float, float, int, tuple[int, int]]] = []
        counter = 0
        heapq.heappush(open_heap, (0.0, heuristic(start_cell), counter, start_cell))
        counter += 1
        g_score: dict[tuple[int, int], float] = {start_cell: 0.0}
        came_from: dict[tuple[int, int], tuple[int, int]] = {}

        while open_heap:
            _, _, _, current = heapq.heappop(open_heap)
            if current == goal_cell:
                path = self._reconstruct(start_cell, goal_cell, came_from)
                return self._replace_terminal_with_goal(path, goal)
            current_g = g_score[current]
            for dx, dy in _DIRECTIONS:
                neighbor = (current[0] + dx, current[1] + dy)
                if not (0 <= neighbor[0] < self.cols and 0 <= neighbor[1] < self.rows):
                    continue
                if self._is_blocked(neighbor):
                    continue
                diagonal = dx != 0 and dy != 0
                if diagonal:
                    # 禁止斜穿两个相邻障碍的夹角。
                    if self._is_blocked((current[0] + dx, current[1])) or self._is_blocked(
                        (current[0], current[1] + dy)
                    ):
                        continue
                step = _DIAGONAL if diagonal else _STRAIGHT
                tentative = current_g + step * self.cell_size + self._clearance_cost(neighbor)
                if tentative < g_score.get(neighbor, float("inf")):
                    g_score[neighbor] = tentative
                    came_from[neighbor] = current
                    heapq.heappush(
                        open_heap,
                        (tentative + heuristic(neighbor) * self.cell_size, heuristic(neighbor), counter, neighbor),
                    )
                    counter += 1
        return None

    def _relax_goal(self, goal_cell: tuple[int, int], radius: int = 4) -> tuple[int, int] | None:
        """在目标格邻域(菱形环)搜索最近可行格。"""

        for ring in range(1, radius + 1):
            for dx in range(-ring, ring + 1):
                for dy in range(-ring, ring + 1):
                    if max(abs(dx), abs(dy)) != ring:
                        continue
                    candidate = (goal_cell[0] + dx, goal_cell[1] + dy)
                    if not (0 <= candidate[0] < self.cols and 0 <= candidate[1] < self.rows):
                        continue
                    if not self._is_blocked(candidate):
                        return candidate
        return None

    def _replace_terminal_with_goal(
        self,
        path: list[tuple[float, float]],
        goal: tuple[float, float],
    ) -> list[tuple[float, float]]:
        """路径末端替换回实际目标点(直线段可行时),否则保留松弛后的终点。"""

        if path and self.walkability.segment_clear(path[-1], goal):
            return path + [goal]
        return path

    def _clearance_cost(self, cell: tuple[int, int]) -> float:
        """净空惩罚:可行邻居越少(越贴墙)代价越高,范围 [0, penalty]。"""

        blocked_neighbors = 0
        for dx, dy in _DIRECTIONS:
            neighbor = (cell[0] + dx, cell[1] + dy)
            if not (0 <= neighbor[0] < self.cols and 0 <= neighbor[1] < self.rows):
                blocked_neighbors += 1
            elif self._is_blocked(neighbor):
                blocked_neighbors += 1
        return self.clearance_penalty * self.cell_size * blocked_neighbors / 8.0

    def _reconstruct(
        self,
        start_cell: tuple[int, int],
        goal_cell: tuple[int, int],
        came_from: dict[tuple[int, int], tuple[int, int]],
    ) -> list[tuple[float, float]]:
        cells: list[tuple[int, int]] = []
        current = goal_cell
        while current != start_cell:
            cells.append(current)
            current = came_from[current]
        cells.append(start_cell)
        cells.reverse()
        return [self.to_point(cell) for cell in cells]

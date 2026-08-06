"""8-direction grid A*.

- Cost = walking distance + a clearance penalty near obstacles (clearance approximated by the number of walkable neighbors).
- Diagonal cutting through the corner between two adjacent obstacles is forbidden: diagonal moves require both orthogonal neighbors to be passable.
- Deterministic tie-breaking: sorted by (f, h, enqueue order), guaranteeing same input -> same output (reproducible).
"""

from __future__ import annotations

import heapq
from array import array
from collections import deque

from .geometry import Point, Rect, point_to_segment_distance
from .walkability import WalkabilityMap, point_to_rect_distance

_STRAIGHT = 1.0
_DIAGONAL = 2 ** 0.5

# Eight directions: 0-3 orthogonal, 4-7 diagonal.
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
        # Grid spatial index: cell -> wall/obstacle indices. Point checks only inspect
        # obstacles in the nearby cells, avoiding full traversal on large scenes (the constant drops from hundreds to a few).
        self._cell_walls: dict[int, list[int]] = {}
        self._cell_obstacles: dict[int, list[int]] = {}
        self._index_obstacles()
        # Reachability pre-check: flood fill from the start marks reachable cells; if the
        # goal is unreachable, fail immediately instead of exploring the whole grid.
        self._reachable_from: tuple[int, int] | None = None
        self._reachable: array | None = None

    # ------------------------------------------------------------------ spatial index

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
        """Rasterize a wall segment onto the grid cells it crosses (stepping by cell_size/2)."""

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
        """Only check obstacles in cells near the given cell (covering the agent-radius range)."""

        col, row = cell
        radius = self.walkability.agent_radius
        span = max(1, int(radius / self.cell_size) + 1)  # cells covered by the inflation radius.
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

    # ------------------------------------------------------------------ grid coordinates

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

    # ------------------------------------------------------------------ reachability pre-check

    def _ensure_reachable(self, start_cell: tuple[int, int]) -> None:
        """Flood fill from the start cell to mark reachable cells; find_path fails immediately when the goal is unreachable."""

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
        """Return the world-coordinate path from start to goal; None when no path exists.

        Goal-cell relaxation: when the goal cell center is not feasible (common for points on doors/boundary lines), search
        the neighborhood for the nearest feasible cell as the endpoint; afterwards, try replacing the path end with the actual goal.
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
            # Octile distance: exact lower bound for 8-direction movement; tighter than Manhattan, fewer expanded cells.
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
                    # Forbid diagonal cutting through the corner between two adjacent obstacles.
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
        """Search the nearest feasible cell in the goal-cell neighborhood (diamond rings)."""

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
        """Replace the path end with the actual goal (when the straight segment is feasible); otherwise keep the relaxed endpoint."""

        if path and self.walkability.segment_clear(path[-1], goal):
            return path + [goal]
        return path

    def _clearance_cost(self, cell: tuple[int, int]) -> float:
        """Clearance penalty: the fewer walkable neighbors (the closer to a wall), the higher the cost; range [0, penalty]."""

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

"""场景语义索引:把 structure.Home 展开为统一全局坐标,并按语义引用解析目标。

坐标约定与 services/map_service.py 一致:
- 顶层区域 bounds 为全局坐标。
- 子区域 bounds 为其父区域渲染坐标系(map_bounds 或默认归一化 0..1)下的局部坐标,
  通过父区域 bounds 归一化映射到全局。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from .geometry import Point, Rect, point_in_rect

# 模糊匹配正则缓存(按 ref key 缓存)。
_WORD_PATTERN_CACHE: dict[str, re.Pattern] = {}


@dataclass(frozen=True, slots=True)
class IndexedArea:
    area_id: str
    name: str
    bounds: Rect  # bounds: 全局坐标。
    parent_id: str | None  # parent_id: 父区域 ID,顶层为 None。
    path: str  # path: 完整层级路径,如 "Block 09 / Student Union / Dining Area"。
    metadata: dict = field(default_factory=dict)
    rendering: dict = field(default_factory=dict)  # rendering: 原始渲染配置,含 map_bounds。


@dataclass(frozen=True, slots=True)
class IndexedElement:
    element_id: str
    name: str
    center: Point  # center: 全局坐标。
    size: tuple[float, float]  # size: 全局尺寸。
    area_id: str  # area_id: 所在区域。
    path: str  # path: 完整层级路径。
    blocks_movement: bool = False
    movable: bool = False


@dataclass(frozen=True, slots=True)
class IndexedPortal:
    portal_id: str
    name: str
    segment: tuple[Point, Point]  # segment: 全局坐标线段。
    center: Point  # center: 门线段中点。
    area_ids: tuple[str, str]  # area_ids: 连接的两个区域。
    open: bool = True  # open: 通行状态(与编辑器 locked 字段区分,导航以 open 为准)。
    channel_id: str | None = None  # channel_id: 同一物理通道的共享标识,缺省为 None。


@dataclass(frozen=True, slots=True)
class IndexedWall:
    wall_id: str
    segment: tuple[Point, Point]  # segment: 全局坐标线段。
    blocks_movement: bool = True


TargetType = Literal["area", "element", "portal"]


@dataclass(frozen=True, slots=True)
class ResolvedDestination:
    ref: str  # ref: 原始语义引用。
    target_type: TargetType  # target_type: 目标类型。
    target_id: str  # target_id: 目标对象 ID。
    area_id: str | None  # area_id: 目标所在区域;目标本身为区域时即自身。
    position: Point  # position: 参考点(区域/元素中心,门中点)。
    bounds: Rect | None  # bounds: 区域或元素全局 bounds;portal 为 None。
    path: str  # path: 目标的完整路径。


def _local_bounds_to_global(bounds: Rect, parent: IndexedArea) -> Rect:
    """把子区域局部 bounds 转换为全局坐标。"""

    local_bounds = parent.rendering.get("map_bounds")
    if local_bounds:
        local_bounds = tuple(float(v) for v in local_bounds)
    else:
        local_bounds = (0.0, 0.0, parent.bounds[2] - parent.bounds[0], parent.bounds[3] - parent.bounds[1])
    local_width = max(1.0, local_bounds[2] - local_bounds[0])
    local_height = max(1.0, local_bounds[3] - local_bounds[1])
    parent_width = parent.bounds[2] - parent.bounds[0]
    parent_height = parent.bounds[3] - parent.bounds[1]

    def to_global(p: Point) -> Point:
        return (
            parent.bounds[0] + (p[0] - local_bounds[0]) * parent_width / local_width,
            parent.bounds[1] + (p[1] - local_bounds[1]) * parent_height / local_height,
        )

    start = to_global((bounds[0], bounds[1]))
    end = to_global((bounds[2], bounds[3]))
    return (start[0], start[1], end[0], end[1])


class SceneSemanticIndex:
    """从 Home 场景对象构建全局语义索引,并提供语义引用解析。"""

    def __init__(self, scene, aliases: dict[str, str] | None = None) -> None:
        self.scene = scene
        self.aliases = {str(key).strip().lower(): str(value).strip() for key, value in (aliases or {}).items()}
        self.areas: dict[str, IndexedArea] = {}
        self.elements: dict[str, IndexedElement] = {}
        self.portals: dict[str, IndexedPortal] = {}
        self.walls: list[IndexedWall] = []
        self.by_name: dict[str, list[str]] = {}  # 小写名称 -> 对象 id 列表(区域/元素/门)。
        self._build()

    # ------------------------------------------------------------------ 构建

    def _build(self) -> None:
        for area in getattr(self.scene, "areas", []):
            self._index_area(area, parent=None, path_prefix="")
        for wall in getattr(self.scene, "walls", []):
            self._index_wall(wall)
        for portal in getattr(self.scene, "portals", []):
            self._index_portal(portal)
        self._index_road_objects()

    def _index_area(self, area, parent: IndexedArea | None, path_prefix: str) -> IndexedArea:
        bounds = tuple(float(v) for v in area.bounds)
        if parent is not None:
            bounds = _local_bounds_to_global(bounds, parent)
        path = f"{path_prefix} / {area.name}".strip(" /") if path_prefix else area.name
        indexed = IndexedArea(
            area_id=area.node_id,
            name=area.name,
            bounds=bounds,
            parent_id=parent.area_id if parent is not None else None,
            path=path,
            metadata=dict(getattr(area, "metadata", {}) or {}),
            rendering=dict(getattr(area, "rendering", {}) or {}),
        )
        self.areas[area.node_id] = indexed
        self._add_name(area.name, f"area:{area.node_id}")
        self._add_name(area.node_id, f"area:{area.node_id}")
        self._add_name(indexed.path, f"area:{area.node_id}")  # 完整层级路径(同建筑过滤/精确解析用)。

        for element in getattr(area, "elements", []):
            center = tuple(float(v) for v in element.center)
            size = tuple(float(v) for v in element.size)
            if parent is not None:
                center = _local_point_to_global(center, parent)
                size = _local_size_to_global(size, parent)
            indexed_element = IndexedElement(
                element_id=element.node_id,
                name=element.name,
                center=center,
                size=size,
                area_id=area.node_id,
                path=f"{path} / {element.name}",
                blocks_movement=bool(getattr(element, "blocks_movement", False)),
                movable=bool(getattr(element, "movable", False)),
            )
            self.elements[element.node_id] = indexed_element
            self._add_name(element.name, f"element:{element.node_id}")
            self._add_name(element.node_id, f"element:{element.node_id}")

        for wall in getattr(area, "walls", []):
            self._index_wall(wall, parent=indexed)

        for portal in getattr(area, "portals", []):
            self._index_portal(portal, parent=indexed)

        for child in getattr(area, "areas", []):
            self._index_area(child, parent=indexed, path_prefix=path)
        return indexed

    def _index_wall(self, wall, parent: IndexedArea | None = None) -> None:
        start, end = _wall_points(wall)
        if parent is not None:
            start = _local_point_to_global(start, parent)
            end = _local_point_to_global(end, parent)
        wall_id = getattr(wall, "wall_id", None) or getattr(wall, "id", None) or "wall"
        self.walls.append(
            IndexedWall(
                wall_id=wall_id,
                segment=(start, end),
                blocks_movement=bool(getattr(wall, "blocks_movement", True)),
            )
        )

    def _index_portal(self, portal, parent: IndexedArea | None = None) -> None:
        segment = getattr(portal, "segment", None)
        if segment is None:
            return
        start = tuple(float(v) for v in segment[0])
        end = tuple(float(v) for v in segment[1])
        if parent is not None:
            start = _local_point_to_global(start, parent)
            end = _local_point_to_global(end, parent)
        portal_id = getattr(portal, "portal_id", None) or getattr(portal, "id", None) or "portal"
        areas = tuple(getattr(portal, "areas", (None, None)) or (None, None))
        indexed = IndexedPortal(
            portal_id=portal_id,
            name=getattr(portal, "name", portal_id),
            segment=(start, end),
            center=((start[0] + end[0]) / 2, (start[1] + end[1]) / 2),
            area_ids=(str(areas[0]), str(areas[1])),
            open=bool(getattr(portal, "open", True)),
            channel_id=getattr(portal, "channel_id", None),
        )
        self.portals[portal_id] = indexed
        self._add_name(indexed.name, f"portal:{portal_id}")
        self._add_name(portal_id, f"portal:{portal_id}")

    def _index_road_objects(self) -> None:
        # 道路对象暂不参与目标解析(road 不作为导航终点);仅登记名称避免歧义。
        for road in getattr(self.scene, "road_segments", []):
            self._add_name(getattr(road, "name", ""), f"road:{getattr(road, 'road_id', '')}")
        for intersection in getattr(self.scene, "road_intersections", []):
            self._add_name(getattr(intersection, "name", ""), f"intersection:{getattr(intersection, 'intersection_id', '')}")

    def _add_name(self, name: str, object_key: str) -> None:
        key = str(name).strip().lower()
        if not key:
            return
        self.by_name.setdefault(key, []).append(object_key)

    # ------------------------------------------------------------------ 查询

    def scene_bounds(self) -> Rect:
        """返回所有区域并集边界;无区域时回退到场景默认出生点附近。"""

        if not self.areas:
            start = getattr(self.scene, "default_agent_start", None) or (0.0, 0.0)
            return (start[0] - 1, start[1] - 1, start[0] + 1, start[1] + 1)
        min_x = min(area.bounds[0] for area in self.areas.values())
        min_y = min(area.bounds[1] for area in self.areas.values())
        max_x = max(area.bounds[2] for area in self.areas.values())
        max_y = max(area.bounds[3] for area in self.areas.values())
        return (min_x, min_y, max_x, max_y)

    def find_area_at(self, point: Point) -> IndexedArea | None:
        """返回包含该点的最深层区域(按层级深度优先匹配)。"""

        best: IndexedArea | None = None
        for area in self.areas.values():
            if point_in_rect(point, area.bounds):
                if best is None or _depth(area) > _depth(best):
                    best = area
        return best

    def get_area(self, area_id: str) -> IndexedArea | None:
        return self.areas.get(area_id)

    def get_element(self, element_id: str) -> IndexedElement | None:
        return self.elements.get(element_id)

    def resolve(self, ref: str) -> ResolvedDestination | None:
        """按语义引用解析目标。

        解析顺序:
        1. 别名(alias -> 标准引用),对别名结果递归解析一次。
        2. 精确 ID / 名称匹配(区域、元素、门),大小写不敏感。
        3. 完整路径匹配("A / B / C"),大小写不敏感。
        4. 末段名称匹配:路径的最后一段唯一命中时采用。
        """

        raw = str(ref or "").strip()
        if not raw:
            return None
        key = raw.lower()
        alias_target = self.aliases.get(key)
        if alias_target is not None and alias_target.lower() != key:
            return self.resolve(alias_target)

        candidates = self.by_name.get(key, [])
        if len(candidates) == 1:
            return self._resolve_key(candidates[0], raw)
        if len(candidates) > 1:
            # 多义名称:优先区域,其次元素,最后门。
            for prefix in ("area:", "element:", "portal:"):
                for candidate in candidates:
                    if candidate.startswith(prefix):
                        return self._resolve_key(candidate, raw)
            return None

        path_candidates = [area for area in self.areas.values() if area.path.lower() == key]
        if len(path_candidates) == 1:
            return self._to_destination(path_candidates[0], raw)
        if len(path_candidates) > 1:
            return None

        for area in self.areas.values():
            if area.path.lower().endswith(f" / {key}") or area.path.lower() == key:
                return self._to_destination(area, raw)
        for element in self.elements.values():
            if element.path.lower().endswith(f" / {key}"):
                return self._to_destination(element, raw)

        # 5. 唯一模糊匹配(LLM 简写/别名兜底):ref 作为独立词出现在名称中,
        #    解析目标按 (类型, 层级深度) 取最优,唯一时采用。
        pattern = _WORD_PATTERN_CACHE.get(key)
        if pattern is None:
            pattern = re.compile(rf"(?<![a-z0-9_/-]){re.escape(key)}(?![a-z0-9_/-])")
            _WORD_PATTERN_CACHE[key] = pattern
        best: dict[str, tuple[int, int, ResolvedDestination]] = {}
        for name, keys in self.by_name.items():
            if not pattern.search(name):
                continue
            for candidate in keys:
                resolved = self._resolve_key(candidate, raw)
                if resolved is None:
                    continue
                rank = 0 if resolved.target_type == "area" else 1 if resolved.target_type == "element" else 2
                depth = 0
                if resolved.target_type == "area":
                    area = self.areas.get(resolved.target_id)
                    depth = area.path.count(" / ") if area is not None else 0
                current = best.get(resolved.target_id)
                if current is None or (rank, depth) < current[:2]:
                    best[resolved.target_id] = (rank, depth, resolved)
        if best:
            best_key = min(best, key=lambda target_id: best[target_id][:2])
            best_value = best[best_key][:2]
            ties = [target_id for target_id in best if best[target_id][:2] == best_value]
            if len(ties) == 1:
                return best[best_key][2]
        return None

    def _resolve_key(self, object_key: str, raw: str) -> ResolvedDestination | None:
        kind, _, object_id = object_key.partition(":")
        if kind == "area":
            area = self.areas.get(object_id)
            return self._to_destination(area, raw) if area else None
        if kind == "element":
            element = self.elements.get(object_id)
            return self._to_destination(element, raw) if element else None
        if kind == "portal":
            portal = self.portals.get(object_id)
            return self._to_destination(portal, raw) if portal else None
        return None

    def _to_destination(self, target, raw: str) -> ResolvedDestination:
        if isinstance(target, IndexedArea):
            return ResolvedDestination(
                ref=raw,
                target_type="area",
                target_id=target.area_id,
                area_id=target.area_id,
                position=_rect_center(target.bounds),
                bounds=target.bounds,
                path=target.path,
            )
        if isinstance(target, IndexedElement):
            area = self.areas.get(target.area_id)
            half_w, half_h = target.size[0] / 2, target.size[1] / 2
            return ResolvedDestination(
                ref=raw,
                target_type="element",
                target_id=target.element_id,
                area_id=target.area_id,
                position=target.center,
                bounds=(target.center[0] - half_w, target.center[1] - half_h, target.center[0] + half_w, target.center[1] + half_h),
                path=target.path,
            )
        return ResolvedDestination(
            ref=raw,
            target_type="portal",
            target_id=target.portal_id,
            area_id=target.area_ids[0] if target.area_ids else None,
            position=target.center,
            bounds=None,
            path=target.name,
        )


# ------------------------------------------------------------------ 工具


def _rect_center(bounds: Rect) -> Point:
    return ((bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2)


def _depth(area: IndexedArea) -> int:
    return area.path.count(" / ")


def _wall_points(wall) -> tuple[Point, Point]:
    segment = getattr(wall, "segment", None)
    if segment:
        return tuple(float(v) for v in segment[0]), tuple(float(v) for v in segment[1])
    return (
        tuple(float(v) for v in getattr(wall, "start", (0.0, 0.0))),
        tuple(float(v) for v in getattr(wall, "end", (0.0, 0.0))),
    )


def _local_point_to_global(point: Point, parent: IndexedArea) -> Point:
    local_bounds = parent.rendering.get("map_bounds")
    if local_bounds:
        local_bounds = tuple(float(v) for v in local_bounds)
    else:
        local_bounds = (0.0, 0.0, parent.bounds[2] - parent.bounds[0], parent.bounds[3] - parent.bounds[1])
    local_width = max(1.0, local_bounds[2] - local_bounds[0])
    local_height = max(1.0, local_bounds[3] - local_bounds[1])
    parent_width = parent.bounds[2] - parent.bounds[0]
    parent_height = parent.bounds[3] - parent.bounds[1]
    return (
        parent.bounds[0] + (point[0] - local_bounds[0]) * parent_width / local_width,
        parent.bounds[1] + (point[1] - local_bounds[1]) * parent_height / local_height,
    )


def _local_size_to_global(size: tuple[float, float], parent: IndexedArea) -> tuple[float, float]:
    local_bounds = parent.rendering.get("map_bounds")
    if local_bounds:
        local_bounds = tuple(float(v) for v in local_bounds)
    else:
        local_bounds = (0.0, 0.0, parent.bounds[2] - parent.bounds[0], parent.bounds[3] - parent.bounds[1])
    local_width = max(1.0, local_bounds[2] - local_bounds[0])
    local_height = max(1.0, local_bounds[3] - local_bounds[1])
    parent_width = parent.bounds[2] - parent.bounds[0]
    parent_height = parent.bounds[3] - parent.bounds[1]
    return (
        size[0] * parent_width / local_width,
        size[1] * parent_height / local_height,
    )

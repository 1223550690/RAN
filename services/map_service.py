from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any


class MapService:
    def get_area_at(self, scene, x: float, y: float) -> dict:
        point = (float(x), float(y))
        area = self._find_area_at(scene.areas, point)
        if area is None:
            return {
                "scene_id": scene.node_id,
                "position": [point[0], point[1]],
                "area": None,
                "child_area": None,
                "space": "outdoor",
                "area_type": None,
            }

        local_point = self._to_local_point(point, area.bounds, self._area_local_bounds(area))
        child_area = self._find_area_at(getattr(area, "areas", []), local_point)
        if child_area is None and getattr(area, "areas", None):
            child_area = self._auto_open_space(area)

        return {
            "scene_id": scene.node_id,
            "position": [point[0], point[1]],
            "local_position": [local_point[0], local_point[1]],
            "area": self._area_summary(area),
            "child_area": self._area_summary(child_area) if child_area else None,
            "space": area.metadata.get("space"),
            "area_type": area.metadata.get("area_type"),
        }

    def get_object_position(self, scene, object_id: str) -> dict | None:
        for area in scene.areas:
            if area.node_id == object_id:
                return self._area_position(area, object_type="area")

            for child_area in getattr(area, "areas", []):
                if child_area.node_id == object_id:
                    return self._area_position(child_area, object_type="child_area", parent_area=area)

            for element in getattr(area, "elements", []):
                if element.node_id == object_id:
                    return self._element_position(element, parent_area=area)

            for child_area in getattr(area, "areas", []):
                for element in getattr(child_area, "elements", []):
                    if element.node_id == object_id:
                        return self._element_position(element, parent_area=area, child_area=child_area)

            for wall in getattr(area, "walls", []):
                if self._field(wall, "wall_id") == object_id:
                    return self._line_position(wall, "wall", "wall_id", parent_area=area)

            for portal in getattr(area, "portals", []):
                if self._field(portal, "portal_id") == object_id or self._field(portal, "id") == object_id:
                    return self._portal_position(portal, parent_area=area)

        for wall in getattr(scene, "walls", []):
            if self._field(wall, "wall_id") == object_id:
                return self._line_position(wall, "wall", "wall_id")

        for portal in getattr(scene, "portals", []):
            if self._field(portal, "portal_id") == object_id or self._field(portal, "id") == object_id:
                return self._portal_position(portal)

        for road in getattr(scene, "road_segments", []):
            if self._field(road, "road_id") == object_id:
                return self._road_position(road)

        for intersection in getattr(scene, "road_intersections", []):
            if self._field(intersection, "intersection_id") == object_id:
                return self._bounds_position(
                    object_id=object_id,
                    object_type="road_intersection",
                    bounds=self._field(intersection, "bounds"),
                )

        return None

    def get_walls_between(self, scene, start: tuple[float, float], end: tuple[float, float]) -> dict:
        start_point = (float(start[0]), float(start[1]))
        end_point = (float(end[0]), float(end[1]))
        walls = []

        for wall in self._iter_global_walls(scene):
            intersection = self._segment_intersection(start_point, end_point, wall["segment"][0], wall["segment"][1])
            if intersection is None:
                continue
            distance = self._distance(start_point, intersection)
            walls.append(
                {
                    **wall,
                    "intersection": [intersection[0], intersection[1]],
                    "distance_from_start": distance,
                }
            )

        walls.sort(key=lambda item: item["distance_from_start"])
        return {
            "scene_id": scene.node_id,
            "start": [start_point[0], start_point[1]],
            "end": [end_point[0], end_point[1]],
            "walls": walls,
        }

    def _find_area_at(self, areas, point: tuple[float, float]):
        for area in reversed(list(areas or [])):
            if self._point_in_bounds(point, area.bounds):
                return area
        return None

    def _iter_global_walls(self, scene):
        for wall in getattr(scene, "walls", []):
            start, end = self._wall_points(wall)
            yield self._wall_summary(
                wall,
                start,
                end,
                scope="scene",
                area=None,
                wall_id=self._field(wall, "wall_id"),
            )

        for area in getattr(scene, "areas", []):
            if area.metadata.get("space") == "indoor":
                for wall in self._area_boundary_walls(area):
                    yield wall

            for wall in getattr(area, "walls", []):
                local_start, local_end = self._wall_points(wall)
                start = self._local_point_to_global(local_start, area)
                end = self._local_point_to_global(local_end, area)
                yield self._wall_summary(
                    wall,
                    start,
                    end,
                    scope="area",
                    area=area,
                    wall_id=self._field(wall, "wall_id"),
                )

    def _area_boundary_walls(self, area):
        min_x, min_y, max_x, max_y = area.bounds
        sides = [
            ("north", (min_x, min_y), (max_x, min_y)),
            ("east", (max_x, min_y), (max_x, max_y)),
            ("south", (min_x, max_y), (max_x, max_y)),
            ("west", (min_x, min_y), (min_x, max_y)),
        ]
        material = area.metadata.get("boundary_material", "exterior_wall")
        loss = float(area.metadata.get("boundary_penetration_loss_db", 20.0))
        for side, start, end in sides:
            wall_id = f"{area.node_id}_boundary_{side}"
            yield {
                "wall_id": wall_id,
                "name": f"{area.name} {side} boundary",
                "area_id": area.node_id,
                "area_name": area.name,
                "scope": "area_boundary",
                "wall_type": "exterior",
                "material": material,
                "thickness_m": 0.2,
                "penetration_loss_db": loss,
                "blocks_signal": True,
                "blocks_movement": True,
                "segment": [[start[0], start[1]], [end[0], end[1]]],
            }

    def _wall_summary(self, wall, start, end, *, scope: str, area, wall_id: str | None) -> dict:
        return {
            "wall_id": wall_id,
            "name": self._field(wall, "name"),
            "area_id": area.node_id if area else None,
            "area_name": area.name if area else None,
            "scope": scope,
            "wall_type": self._field(wall, "wall_type"),
            "material": self._field(wall, "material"),
            "thickness_m": self._field(wall, "thickness_m"),
            "penetration_loss_db": self._field(wall, "penetration_loss_db"),
            "blocks_signal": True,
            "blocks_movement": bool(self._field(wall, "blocks_movement")),
            "segment": [[start[0], start[1]], [end[0], end[1]]],
        }

    def _wall_points(self, wall) -> tuple[tuple[float, float], tuple[float, float]]:
        segment = self._field(wall, "segment")
        if segment:
            return tuple(segment[0]), tuple(segment[1])
        return tuple(self._field(wall, "start")), tuple(self._field(wall, "end"))

    def _segment_intersection(
        self,
        a: tuple[float, float],
        b: tuple[float, float],
        c: tuple[float, float],
        d: tuple[float, float],
    ) -> tuple[float, float] | None:
        ax, ay = a
        bx, by = b
        cx, cy = c
        dx, dy = d
        r = (bx - ax, by - ay)
        s = (dx - cx, dy - cy)
        denominator = self._cross(r, s)
        q_minus_p = (cx - ax, cy - ay)

        if abs(denominator) < 1e-9:
            if abs(self._cross(q_minus_p, r)) >= 1e-9:
                return None
            return self._collinear_overlap_point(a, b, c, d)

        t = self._cross(q_minus_p, s) / denominator
        u = self._cross(q_minus_p, r) / denominator
        if -1e-9 <= t <= 1 + 1e-9 and -1e-9 <= u <= 1 + 1e-9:
            return (ax + t * r[0], ay + t * r[1])
        return None

    def _collinear_overlap_point(self, a, b, c, d) -> tuple[float, float] | None:
        ab = (b[0] - a[0], b[1] - a[1])
        length_sq = ab[0] * ab[0] + ab[1] * ab[1]
        if length_sq < 1e-9:
            return a if self._point_on_segment(a, c, d) else None
        t1 = ((c[0] - a[0]) * ab[0] + (c[1] - a[1]) * ab[1]) / length_sq
        t2 = ((d[0] - a[0]) * ab[0] + (d[1] - a[1]) * ab[1]) / length_sq
        start_t = max(0.0, min(t1, t2))
        end_t = min(1.0, max(t1, t2))
        if start_t <= end_t + 1e-9:
            return (a[0] + start_t * ab[0], a[1] + start_t * ab[1])
        return None

    @staticmethod
    def _point_on_segment(point, start, end) -> bool:
        return (
            min(start[0], end[0]) - 1e-9 <= point[0] <= max(start[0], end[0]) + 1e-9
            and min(start[1], end[1]) - 1e-9 <= point[1] <= max(start[1], end[1]) + 1e-9
        )

    @staticmethod
    def _cross(a, b) -> float:
        return a[0] * b[1] - a[1] * b[0]

    @staticmethod
    def _distance(a, b) -> float:
        return ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5

    @staticmethod
    def _point_in_bounds(point: tuple[float, float], bounds) -> bool:
        x, y = point
        min_x, min_y, max_x, max_y = bounds
        return min_x <= x <= max_x and min_y <= y <= max_y

    @staticmethod
    def _to_local_point(point, parent_bounds, local_bounds) -> tuple[float, float]:
        parent_width = max(1.0, parent_bounds[2] - parent_bounds[0])
        parent_height = max(1.0, parent_bounds[3] - parent_bounds[1])
        local_width = max(1.0, local_bounds[2] - local_bounds[0])
        local_height = max(1.0, local_bounds[3] - local_bounds[1])
        return (
            local_bounds[0] + (point[0] - parent_bounds[0]) * local_width / parent_width,
            local_bounds[1] + (point[1] - parent_bounds[1]) * local_height / parent_height,
        )

    @staticmethod
    def _area_local_bounds(area) -> tuple[float, float, float, float]:
        bounds = area.rendering.get("map_bounds") if getattr(area, "rendering", None) else None
        if bounds:
            return tuple(bounds)
        return (0.0, 0.0, area.bounds[2] - area.bounds[0], area.bounds[3] - area.bounds[1])

    def _area_summary(self, area) -> dict:
        if isinstance(area, dict):
            metadata = area.get("metadata", {})
            return {
                "id": area.get("node_id"),
                "name": area.get("name"),
                "bounds": list(area.get("bounds", [])),
                "space": metadata.get("space"),
                "area_type": metadata.get("area_type"),
            }
        return {
            "id": area.node_id,
            "name": area.name,
            "bounds": list(area.bounds),
            "space": area.metadata.get("space"),
            "area_type": area.metadata.get("area_type"),
        }

    def _auto_open_space(self, area) -> dict:
        return {
            "node_id": f"{area.node_id}_open_space",
            "name": f"{area.name} open space",
            "bounds": self._area_local_bounds(area),
            "metadata": {
                "space": area.metadata.get("space"),
                "area_type": "open_space",
                "source": "auto_open_space",
            },
        }

    def _area_position(self, area, *, object_type: str, parent_area=None) -> dict:
        result = self._bounds_position(object_id=area.node_id, object_type=object_type, bounds=area.bounds)
        if parent_area is not None:
            result["parent_area_id"] = parent_area.node_id
            result["local_bounds"] = result.pop("bounds")
            result["local_center"] = result.pop("center")
            result["bounds"] = self._local_bounds_to_global(result["local_bounds"], parent_area)
            result["center"] = [
                (result["bounds"][0] + result["bounds"][2]) / 2,
                (result["bounds"][1] + result["bounds"][3]) / 2,
            ]
        return result

    def _bounds_position(self, *, object_id: str, object_type: str, bounds) -> dict:
        bounds = list(bounds)
        return {
            "object_id": object_id,
            "object_type": object_type,
            "bounds": bounds,
            "center": [(bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2],
        }

    def _element_position(self, element, *, parent_area, child_area=None) -> dict:
        result = {
            "object_id": element.node_id,
            "object_type": "element",
            "center": list(element.center),
            "size": list(element.size),
            "parent_area_id": parent_area.node_id,
        }
        if child_area is not None:
            result["child_area_id"] = child_area.node_id
            result["local_center"] = result["center"]
            result["local_size"] = result["size"]
            result["center"] = list(self._local_point_to_global(result["local_center"], parent_area))
            result["size"] = list(self._local_size_to_global(result["local_size"], parent_area))
        return result

    def _line_position(self, item, object_type: str, id_field: str, *, parent_area=None) -> dict:
        start, end = self._wall_points(item)
        result = {
            "object_id": self._field(item, id_field),
            "object_type": object_type,
            "segment": [list(start), list(end)],
        }
        if parent_area is not None:
            result["parent_area_id"] = parent_area.node_id
            result["local_segment"] = result["segment"]
            result["segment"] = [list(self._local_point_to_global(point, parent_area)) for point in result["local_segment"]]
        return result

    def _portal_position(self, portal, *, parent_area=None) -> dict:
        portal_id = self._field(portal, "portal_id") or self._field(portal, "id")
        segment = self._field(portal, "segment")
        result = {
            "object_id": portal_id,
            "object_type": "portal",
            "segment": [list(segment[0]), list(segment[1])],
            "center": [(segment[0][0] + segment[1][0]) / 2, (segment[0][1] + segment[1][1]) / 2],
        }
        if parent_area is not None:
            result["parent_area_id"] = parent_area.node_id
            result["local_segment"] = result["segment"]
            result["local_center"] = result["center"]
            result["segment"] = [list(self._local_point_to_global(point, parent_area)) for point in result["local_segment"]]
            result["center"] = list(self._local_point_to_global(result["local_center"], parent_area))
        return result

    def _local_bounds_to_global(self, bounds, parent_area) -> list[float]:
        start = self._local_point_to_global((bounds[0], bounds[1]), parent_area)
        end = self._local_point_to_global((bounds[2], bounds[3]), parent_area)
        return [start[0], start[1], end[0], end[1]]

    def _local_point_to_global(self, point, parent_area) -> tuple[float, float]:
        local_bounds = self._area_local_bounds(parent_area)
        local_width = max(1.0, local_bounds[2] - local_bounds[0])
        local_height = max(1.0, local_bounds[3] - local_bounds[1])
        parent_width = parent_area.bounds[2] - parent_area.bounds[0]
        parent_height = parent_area.bounds[3] - parent_area.bounds[1]
        return (
            parent_area.bounds[0] + (point[0] - local_bounds[0]) * parent_width / local_width,
            parent_area.bounds[1] + (point[1] - local_bounds[1]) * parent_height / local_height,
        )

    def _local_size_to_global(self, size, parent_area) -> tuple[float, float]:
        local_bounds = self._area_local_bounds(parent_area)
        local_width = max(1.0, local_bounds[2] - local_bounds[0])
        local_height = max(1.0, local_bounds[3] - local_bounds[1])
        parent_width = parent_area.bounds[2] - parent_area.bounds[0]
        parent_height = parent_area.bounds[3] - parent_area.bounds[1]
        return (
            size[0] * parent_width / local_width,
            size[1] * parent_height / local_height,
        )

    def _road_position(self, road) -> dict:
        top = self._field(road, "top")
        bottom = self._field(road, "bottom")
        points = [
            [top["x1"], top["y"]],
            [top["x2"], top["y"]],
            [bottom["x2"], bottom["y"]],
            [bottom["x1"], bottom["y"]],
        ]
        return {
            "object_id": self._field(road, "road_id"),
            "object_type": "road_segment",
            "polygon": points,
            "center": [
                sum(point[0] for point in points) / len(points),
                sum(point[1] for point in points) / len(points),
            ],
        }

    @staticmethod
    def _field(item: Any, field_name: str):
        if isinstance(item, dict):
            return item.get(field_name)
        if is_dataclass(item):
            return asdict(item).get(field_name)
        return getattr(item, field_name, None)

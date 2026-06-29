from __future__ import annotations

from .scene_schema import Area, Element, Home, Portal, RoadIntersection, RoadSegment, WallSegment


def build_scene_tree(
    *,
    scene_id: str,
    scene_name: str,
    area_definitions: list[tuple[str, str, tuple[float, float, float, float]]],
    area_elements: dict[str, list[dict]],
    blocking_element_ids: set[str] | None = None,
    default_agent_start: tuple[float, float] | None = None,
    portal_definitions: list[dict] | None = None,
    wall_definitions: list[dict] | None = None,
    road_segment_definitions: list[dict] | None = None,
    road_intersection_definitions: list[dict] | None = None,
    rendering: dict | None = None,
    area_metadata: dict[str, dict] | None = None,
) -> Home:
    scene = Home(
        node_id=scene_id,
        name=scene_name,
        default_agent_start=default_agent_start,
        portals=[build_portal(item) for item in portal_definitions or []],
        walls=[build_wall_segment(item) for item in wall_definitions or []],
        road_segments=[build_road_segment(item) for item in road_segment_definitions or []],
        road_intersections=[build_road_intersection(item) for item in road_intersection_definitions or []],
        rendering=dict(rendering or {}),
    )
    blocking_ids = blocking_element_ids or set()
    metadata_by_area = area_metadata or {}

    for area_id, area_name, bounds in area_definitions:
        area = Area(area_id, area_name, bounds, metadata=dict(metadata_by_area.get(area_id, {})))
        for item in area_elements.get(area_id, []):
            area.add(
                Element(
                    node_id=item["node_id"],
                    name=item["name"],
                    center=item["center"],
                    size=item["size"],
                    movable=item.get("movable", False),
                    locked=item.get("locked", False),
                    blocks_movement=item.get("blocks_movement", item["node_id"] in blocking_ids),
                    physical_status=item.get("physical_status", item.get("status", "regular")),
                    evolution_status=item.get("evolution_status", "stable"),
                    interaction_status=item.get("interaction_status", "idle"),
                    state_details=dict(item.get("state_details", {}) or {}),
                )
            )
        scene.add(area)

    return scene


def build_portal(item: dict) -> Portal:
    segment = item["segment"]
    areas = tuple(item.get("areas") or endpoint_area_ids(item.get("endpoints", [])))
    portal_id = item.get("portal_id") or item.get("id")
    return Portal(
        portal_id=portal_id,
        name=item.get("name", portal_id or "portal"),
        kind=item.get("kind", "opening"),
        role=item.get("role", "passage"),
        locked=item.get("locked", False),
        areas=areas,
        endpoints=tuple(dict(endpoint) for endpoint in item.get("endpoints", [])) if item.get("endpoints") else None,
        segment=(tuple(segment[0]), tuple(segment[1])),
        wall_id=item.get("wall_id"),
        width_m=item.get("width_m"),
        open=item.get("open", True),
    )


def endpoint_area_ids(endpoints: list[dict]) -> tuple[str, str]:
    ids = [endpoint.get("object_id", "") for endpoint in endpoints[:2]]
    while len(ids) < 2:
        ids.append("")
    return tuple(ids)


def build_wall_segment(item: dict) -> WallSegment:
    wall_id = item.get("wall_id") or item.get("id")
    return WallSegment(
        wall_id=wall_id,
        name=item.get("name", wall_id or "wall"),
        start=tuple(item["start"]),
        end=tuple(item["end"]),
        wall_type=item.get("wall_type", "interior"),
        material=item.get("material", "drywall"),
        thickness_m=item.get("thickness_m", 0.2),
        penetration_loss_db=item.get("penetration_loss_db", 5.0),
        blocks_movement=item.get("blocks_movement", True),
        locked=item.get("locked", False),
        areas=tuple(item.get("areas", (None, None))),
        portal_ids=list(item.get("portal_ids", [])),
    )


def build_road_segment(item: dict) -> RoadSegment:
    road_id = item.get("road_id") or item.get("id")
    return RoadSegment(
        road_id=road_id,
        name=item.get("name", road_id or "road"),
        top=dict(item["top"]),
        bottom=dict(item["bottom"]),
        road_type=item.get("road_type", "pedestrian"),
        walkable=item.get("walkable", True),
        locked=item.get("locked", False),
        metadata=dict(item.get("metadata", {}) or {}),
    )


def build_road_intersection(item: dict) -> RoadIntersection:
    intersection_id = item.get("intersection_id") or item.get("id")
    return RoadIntersection(
        intersection_id=intersection_id,
        name=item.get("name", intersection_id or "intersection"),
        bounds=tuple(item["bounds"]),
        connected_roads=list(item.get("connected_roads", [])),
        road_type=item.get("road_type", "junction"),
        walkable=item.get("walkable", True),
        locked=item.get("locked", False),
        metadata=dict(item.get("metadata", {}) or {}),
    )


def build_home_tree() -> Home:
    from .scenes.home.scene import build_home_tree as build

    return build()


if __name__ == "__main__":
    import json

    tree = build_home_tree()
    print(json.dumps(tree.to_dict(), ensure_ascii=False, indent=2))
    print()
    tree.print_tree()

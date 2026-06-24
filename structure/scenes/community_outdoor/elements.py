from __future__ import annotations

from ...scene_schema import Home
from ..home.scene import build_home_tree
from ..office.scene import build_office_tree
from ..potions_teacher_office.scene import build_potions_teacher_office_tree


def transformed_scene_elements(source: Home, *, prefix: str, target_bounds: tuple[float, float, float, float]) -> list[dict]:
    source_bounds = scene_bounds(source)
    source_min_x, source_min_y, source_max_x, source_max_y = source_bounds
    target_min_x, target_min_y, target_max_x, target_max_y = target_bounds
    source_width = source_max_x - source_min_x
    source_height = source_max_y - source_min_y
    target_width = target_max_x - target_min_x
    target_height = target_max_y - target_min_y
    scale = min(target_width / source_width, target_height / source_height)
    used_width = source_width * scale
    used_height = source_height * scale
    offset_x = target_min_x + (target_width - used_width) / 2
    offset_y = target_min_y + (target_height - used_height) / 2

    elements: list[dict] = []
    for area in source.areas:
        area_min_x, area_min_y, area_max_x, area_max_y = area.bounds
        area_center = (
            offset_x + (area_min_x + area_max_x - source_min_x * 2) * scale / 2,
            offset_y + (area_min_y + area_max_y - source_min_y * 2) * scale / 2,
        )
        area_size = ((area_max_x - area_min_x) * scale, (area_max_y - area_min_y) * scale)
        elements.append(
            {
                "node_id": f"{prefix}_area_{area.node_id}",
                "name": f"{source.name} / {area.name}",
                "center": round_point(area_center),
                "size": round_point(area_size),
                "status": "regular",
                "movable": False,
                "blocks_movement": False,
                "state_details": {"source_scene": source.node_id, "source_area": area.node_id, "preview_kind": "area"},
            }
        )

        for element in area.elements:
            center = (
                offset_x + (element.center[0] - source_min_x) * scale,
                offset_y + (element.center[1] - source_min_y) * scale,
            )
            size = (element.size[0] * scale, element.size[1] * scale)
            elements.append(
                {
                    "node_id": f"{prefix}_{element.node_id}",
                    "name": element.name,
                    "center": round_point(center),
                    "size": round_point(size),
                    "status": element.physical_status,
                    "movable": element.movable,
                    "blocks_movement": element.blocks_movement,
                    "evolution_status": element.evolution_status,
                    "interaction_status": element.interaction_status,
                    "state_details": {
                        **element.state_details,
                        "source_scene": source.node_id,
                        "source_area": area.node_id,
                        "source_element": element.node_id,
                    },
                }
            )
    return elements


def scene_bounds(scene: Home) -> tuple[float, float, float, float]:
    min_x = min(area.bounds[0] for area in scene.areas)
    min_y = min(area.bounds[1] for area in scene.areas)
    max_x = max(area.bounds[2] for area in scene.areas)
    max_y = max(area.bounds[3] for area in scene.areas)
    return min_x, min_y, max_x, max_y


def round_point(point: tuple[float, float]) -> tuple[float, float]:
    return (round(point[0], 3), round(point[1], 3))


AREA_ELEMENTS = {
    "home_indoor_region": transformed_scene_elements(
        build_home_tree(),
        prefix="home",
        target_bounds=(2.0, 32.0, 22.0, 57.0),
    ),
    "office_indoor_region": transformed_scene_elements(
        build_office_tree(),
        prefix="office",
        target_bounds=(29.0, 32.0, 51.0, 57.0),
    ),
    "potions_teacher_office_indoor_region": transformed_scene_elements(
        build_potions_teacher_office_tree(),
        prefix="potions",
        target_bounds=(58.0, 32.0, 78.0, 57.0),
    ),
}


COMMUNITY_OUTDOOR_BLOCKING_ELEMENT_IDS = {
    item["node_id"]
    for elements in AREA_ELEMENTS.values()
    for item in elements
    if item.get("blocks_movement")
}

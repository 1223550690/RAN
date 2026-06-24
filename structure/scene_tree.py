from __future__ import annotations

from .scene_schema import Area, Element, Home


def build_scene_tree(
    *,
    scene_id: str,
    scene_name: str,
    area_definitions: list[tuple[str, str, tuple[float, float, float, float]]],
    area_elements: dict[str, list[dict]],
    blocking_element_ids: set[str] | None = None,
    default_agent_start: tuple[float, float] | None = None,
    portal_definitions: list[dict] | None = None,
    rendering: dict | None = None,
    area_metadata: dict[str, dict] | None = None,
) -> Home:
    scene = Home(
        node_id=scene_id,
        name=scene_name,
        default_agent_start=default_agent_start,
        portals=[dict(item) for item in portal_definitions or []],
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
                    blocks_movement=item.get("blocks_movement", item["node_id"] in blocking_ids),
                    physical_status=item.get("physical_status", item.get("status", "regular")),
                    evolution_status=item.get("evolution_status", "stable"),
                    interaction_status=item.get("interaction_status", "idle"),
                    state_details=dict(item.get("state_details", {}) or {}),
                )
            )
        scene.add(area)

    return scene


def build_home_tree() -> Home:
    from .scenes.home.scene import build_home_tree as build

    return build()


if __name__ == "__main__":
    import json

    tree = build_home_tree()
    print(json.dumps(tree.to_dict(), ensure_ascii=False, indent=2))
    print()
    tree.print_tree()

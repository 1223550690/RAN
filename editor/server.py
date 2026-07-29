from __future__ import annotations

import argparse
import json
import keyword
import re
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from pprint import pformat
from urllib.parse import urlparse


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCENES_ROOT = (PROJECT_ROOT / "editor" / "data" / "scenes").resolve()
STRUCTURE_SCENES_ROOT = (PROJECT_ROOT / "structure" / "scenes").resolve()
SCENE_REGISTRY_PATH = PROJECT_ROOT / "structure" / "scene_registry.py"


class EditorRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PROJECT_ROOT), **kwargs)

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/scenes/save":
            self.send_error(HTTPStatus.NOT_FOUND, "Unknown API endpoint")
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            scene_path = resolve_scene_path(payload.get("path"))
            scene = payload["scene"]
            scene_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = scene_path.with_suffix(scene_path.suffix + ".tmp")
            temp_path.write_text(json.dumps(scene, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            temp_path.replace(scene_path)
            write_structure_scene(scene)
            update_scene_registry()
        except Exception as exc:
            self.send_response(HTTPStatus.BAD_REQUEST)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(str(exc).encode("utf-8"))
            return

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(b'{"ok": true}')


def resolve_scene_path(raw_path: str | None) -> Path:
    if not raw_path:
        raise ValueError("Missing scene path")
    relative = raw_path.removeprefix("./").replace("/", "\\")
    path = (PROJECT_ROOT / "editor" / relative).resolve() if relative.startswith("data\\") else (PROJECT_ROOT / relative).resolve()
    if path.suffix.lower() != ".json":
        raise ValueError("Only JSON scene files can be saved")
    if not path.is_relative_to(SCENES_ROOT):
        raise ValueError("Scene path is outside editor/data/scenes")
    return path


def write_structure_scene(scene: dict) -> None:
    scene_id = scene["node_id"]
    scene_name = scene.get("name", scene_id)
    package_name = safe_identifier(scene_id)
    builder_name = f"build_{package_name}_tree"
    scene_dir = STRUCTURE_SCENES_ROOT / package_name
    scene_dir.mkdir(parents=True, exist_ok=True)

    area_definitions = [
        (area["node_id"], area.get("name", area["node_id"]), tuple(area.get("bounds", (0, 0, 1, 1))))
        for area in scene.get("areas", [])
    ]
    area_metadata = {
        area["node_id"]: dict(area.get("metadata", {}) or {})
        for area in scene.get("areas", [])
    }
    area_elements = {
        area["node_id"]: [normalize_element_for_python(element) for element in area.get("elements", [])]
        for area in scene.get("areas", [])
        if area.get("elements")
    }
    area_child_areas = {
        area["node_id"]: [normalize_area_for_python(child) for child in area.get("areas", [])]
        for area in scene.get("areas", [])
        if area.get("areas")
    }
    area_wall_definitions = {
        area["node_id"]: area.get("walls", [])
        for area in scene.get("areas", [])
        if area.get("walls")
    }
    area_portal_definitions = {
        area["node_id"]: area.get("portals", [])
        for area in scene.get("areas", [])
        if area.get("portals")
    }
    area_rendering = {
        area["node_id"]: area.get("rendering", {})
        for area in scene.get("areas", [])
        if area.get("rendering")
    }
    blocking_ids = {
        element["node_id"]
        for area in scene.get("areas", [])
        for element in area.get("elements", [])
        if element.get("blocks_movement")
    }
    roads = scene.get("roads", {}) or {}

    (scene_dir / "__init__.py").write_text(
        f"from .scene import {builder_name}\n\n__all__ = [\"{builder_name}\"]\n",
        encoding="utf-8",
    )
    (scene_dir / "elements.py").write_text(
        generated_header()
        + f"AREA_ELEMENTS = {python_literal(area_elements)}\n\n"
        + f"{package_name.upper()}_BLOCKING_ELEMENT_IDS = {python_literal(blocking_ids)}\n",
        encoding="utf-8",
    )
    (scene_dir / "layout.py").write_text(
        generated_header()
        + f"AREA_DEFINITIONS = {python_literal(area_definitions)}\n\n"
        + f"AREA_METADATA = {python_literal(area_metadata)}\n\n"
        + f"AREA_CHILD_AREAS = {python_literal(area_child_areas)}\n\n"
        + f"AREA_WALL_DEFINITIONS = {python_literal(area_wall_definitions)}\n\n"
        + f"AREA_PORTAL_DEFINITIONS = {python_literal(area_portal_definitions)}\n\n"
        + f"AREA_RENDERING = {python_literal(area_rendering)}\n\n"
        + f"PORTAL_DEFINITIONS = {python_literal(scene.get('portals', []))}\n\n"
        + f"WALL_DEFINITIONS = {python_literal(scene.get('walls', []))}\n\n"
        + f"ROAD_SEGMENT_DEFINITIONS = {python_literal(roads.get('segments', []))}\n\n"
        + f"ROAD_INTERSECTION_DEFINITIONS = {python_literal(roads.get('intersections', []))}\n\n"
        + f"RENDERING = {python_literal(scene.get('rendering', {}))}\n\n"
        + f"{package_name.upper()}_DEFAULT_AGENT_START = {python_literal(scene.get('default_agent_start'))}\n",
        encoding="utf-8",
    )
    (scene_dir / "scene.py").write_text(
        generated_header()
        + "from __future__ import annotations\n\n"
        + "from ...scene_schema import Home\n"
        + "from ...scene_tree import build_scene_tree\n\n"
        + f"from .elements import AREA_ELEMENTS, {package_name.upper()}_BLOCKING_ELEMENT_IDS\n"
        + "from .layout import (\n"
        + "    AREA_DEFINITIONS,\n"
        + "    AREA_CHILD_AREAS,\n"
        + "    AREA_METADATA,\n"
        + "    AREA_PORTAL_DEFINITIONS,\n"
        + "    AREA_RENDERING,\n"
        + "    AREA_WALL_DEFINITIONS,\n"
        + f"    {package_name.upper()}_DEFAULT_AGENT_START,\n"
        + "    PORTAL_DEFINITIONS,\n"
        + "    RENDERING,\n"
        + "    ROAD_INTERSECTION_DEFINITIONS,\n"
        + "    ROAD_SEGMENT_DEFINITIONS,\n"
        + "    WALL_DEFINITIONS,\n"
        + ")\n\n\n"
        + f"def {builder_name}() -> Home:\n"
        + "    return build_scene_tree(\n"
        + f"        scene_id={scene_id!r},\n"
        + f"        scene_name={scene_name!r},\n"
        + "        area_definitions=AREA_DEFINITIONS,\n"
        + "        area_elements=AREA_ELEMENTS,\n"
        + f"        blocking_element_ids={package_name.upper()}_BLOCKING_ELEMENT_IDS,\n"
        + f"        default_agent_start={package_name.upper()}_DEFAULT_AGENT_START,\n"
        + "        portal_definitions=PORTAL_DEFINITIONS,\n"
        + "        wall_definitions=WALL_DEFINITIONS,\n"
        + "        road_segment_definitions=ROAD_SEGMENT_DEFINITIONS,\n"
        + "        road_intersection_definitions=ROAD_INTERSECTION_DEFINITIONS,\n"
        + "        rendering=RENDERING,\n"
        + "        area_metadata=AREA_METADATA,\n"
        + "        area_child_areas=AREA_CHILD_AREAS,\n"
        + "        area_wall_definitions=AREA_WALL_DEFINITIONS,\n"
        + "        area_portal_definitions=AREA_PORTAL_DEFINITIONS,\n"
        + "        area_rendering=AREA_RENDERING,\n"
        + "    )\n",
        encoding="utf-8",
    )
    (scene_dir / "README.md").write_text(
        f"# {scene_name}\n\n"
        "This structure scene package is generated from the scene editor JSON.\n"
        "Manual edits may be overwritten the next time the editor saves this scene.\n",
        encoding="utf-8",
    )


def update_scene_registry() -> None:
    packages = sorted(
        path.name
        for path in STRUCTURE_SCENES_ROOT.iterdir()
        if path.is_dir() and (path / "scene.py").exists() and not path.name.startswith("__")
    )
    imports = "\n".join(
        f"from .scenes.{name} import build_{name}_tree"
        for name in packages
    )
    builders = "\n".join(
        f"    {name!r}: build_{name}_tree,"
        for name in packages
    )
    SCENE_REGISTRY_PATH.write_text(
        "from __future__ import annotations\n\n"
        "from collections.abc import Callable\n\n"
        "from .scene_schema import Home\n"
        f"{imports}\n\n\n"
        "SceneBuilder = Callable[[], Home]\n\n\n"
        "SCENE_BUILDERS: dict[str, SceneBuilder] = {\n"
        f"{builders}\n"
        "}\n\n\n"
        "def available_scene_names() -> list[str]:\n"
        "    return sorted(SCENE_BUILDERS)\n\n\n"
        "def build_scene(scene_name: str) -> Home:\n"
        "    try:\n"
        "        builder = SCENE_BUILDERS[scene_name]\n"
        "    except KeyError as exc:\n"
        "        choices = \", \".join(available_scene_names())\n"
        "        raise ValueError(f\"Unknown scene '{scene_name}'. Available scenes: {choices}\") from exc\n"
        "    return builder()\n",
        encoding="utf-8",
    )


def normalize_element_for_python(element: dict) -> dict:
    return {
        "node_id": element["node_id"],
        "name": element.get("name", element["node_id"]),
        "center": tuple(element.get("center", (0, 0))),
        "size": tuple(element.get("size", (1, 1))),
        "movable": element.get("movable", True),
        "locked": element.get("locked", False),
        "blocks_movement": element.get("blocks_movement", False),
        "physical_status": element.get("physical_status", element.get("status", "regular")),
        "evolution_status": element.get("evolution_status", "stable"),
        "interaction_status": element.get("interaction_status", "idle"),
        "state_details": dict(element.get("state_details", {}) or {}),
    }


def normalize_area_for_python(area: dict) -> dict:
    return {
        "node_id": area["node_id"],
        "name": area.get("name", area["node_id"]),
        "bounds": tuple(area.get("bounds", (0, 0, 1, 1))),
        "metadata": dict(area.get("metadata", {}) or {}),
        "elements": [normalize_element_for_python(element) for element in area.get("elements", [])],
        "areas": [normalize_area_for_python(child) for child in area.get("areas", [])],
        "portals": list(area.get("portals", []) or []),
        "walls": list(area.get("walls", []) or []),
        "rendering": dict(area.get("rendering", {}) or {}),
    }


def safe_identifier(value: str) -> str:
    cleaned = re.sub(r"\W+", "_", value).strip("_").lower()
    if not cleaned or cleaned[0].isdigit() or keyword.iskeyword(cleaned):
        cleaned = f"scene_{cleaned}"
    return cleaned


def python_literal(value) -> str:
    return pformat(value, width=100, sort_dicts=False)


def generated_header() -> str:
    return "# Auto-generated by editor.server from editor/data/scenes/*.json.\n# Do not edit manually.\n\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the writable local scene editor server.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), EditorRequestHandler)
    print(f"editor=http://{args.host}:{args.port}/editor/", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()

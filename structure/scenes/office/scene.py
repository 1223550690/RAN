from __future__ import annotations

from ...scene_schema import Home
from ...scene_tree import build_scene_tree

from .elements import AREA_ELEMENTS, OFFICE_BLOCKING_ELEMENT_IDS
from .layout import AREA_DEFINITIONS, OFFICE_DEFAULT_AGENT_START, PORTAL_DEFINITIONS, RENDERING


def build_office_tree() -> Home:
    return build_scene_tree(
        scene_id="office",
        scene_name="single_office",
        area_definitions=AREA_DEFINITIONS,
        area_elements=AREA_ELEMENTS,
        blocking_element_ids=OFFICE_BLOCKING_ELEMENT_IDS,
        default_agent_start=OFFICE_DEFAULT_AGENT_START,
        portal_definitions=PORTAL_DEFINITIONS,
        rendering=RENDERING,
    )

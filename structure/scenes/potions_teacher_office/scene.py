from __future__ import annotations

from ...scene_schema import Home
from ...scene_tree import build_scene_tree

from .elements import AREA_ELEMENTS, POTIONS_TEACHER_OFFICE_BLOCKING_ELEMENT_IDS
from .layout import (
    AREA_DEFINITIONS,
    PORTAL_DEFINITIONS,
    POTIONS_TEACHER_OFFICE_DEFAULT_AGENT_START,
    RENDERING,
)


def build_potions_teacher_office_tree() -> Home:
    return build_scene_tree(
        scene_id="potions_teacher_office",
        scene_name="魔药课教师办公室",
        area_definitions=AREA_DEFINITIONS,
        area_elements=AREA_ELEMENTS,
        blocking_element_ids=POTIONS_TEACHER_OFFICE_BLOCKING_ELEMENT_IDS,
        default_agent_start=POTIONS_TEACHER_OFFICE_DEFAULT_AGENT_START,
        portal_definitions=PORTAL_DEFINITIONS,
        rendering=RENDERING,
    )

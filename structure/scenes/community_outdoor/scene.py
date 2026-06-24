from __future__ import annotations

from ...scene_schema import Home
from ...scene_tree import build_scene_tree

from .elements import AREA_ELEMENTS, COMMUNITY_OUTDOOR_BLOCKING_ELEMENT_IDS
from .layout import (
    AREA_DEFINITIONS,
    AREA_METADATA,
    COMMUNITY_OUTDOOR_DEFAULT_AGENT_START,
    PORTAL_DEFINITIONS,
    RENDERING,
)


def build_community_outdoor_tree() -> Home:
    return build_scene_tree(
        scene_id="community_outdoor",
        scene_name="社区级室内外平面图",
        area_definitions=AREA_DEFINITIONS,
        area_elements=AREA_ELEMENTS,
        blocking_element_ids=COMMUNITY_OUTDOOR_BLOCKING_ELEMENT_IDS,
        default_agent_start=COMMUNITY_OUTDOOR_DEFAULT_AGENT_START,
        portal_definitions=PORTAL_DEFINITIONS,
        rendering=RENDERING,
        area_metadata=AREA_METADATA,
    )

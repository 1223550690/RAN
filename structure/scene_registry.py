from __future__ import annotations

from collections.abc import Callable

from .scene_schema import Home
from .scenes.community_outdoor import build_community_outdoor_tree
from .scenes.home import build_home_tree
from .scenes.office import build_office_tree
from .scenes.potions_teacher_office import build_potions_teacher_office_tree


SceneBuilder = Callable[[], Home]


SCENE_BUILDERS: dict[str, SceneBuilder] = {
    "community_outdoor": build_community_outdoor_tree,
    "home": build_home_tree,
    "office": build_office_tree,
    "potions_teacher_office": build_potions_teacher_office_tree,
}


def available_scene_names() -> list[str]:
    return sorted(SCENE_BUILDERS)


def build_scene(scene_name: str) -> Home:
    try:
        builder = SCENE_BUILDERS[scene_name]
    except KeyError as exc:
        choices = ", ".join(available_scene_names())
        raise ValueError(f"Unknown scene '{scene_name}'. Available scenes: {choices}") from exc
    return builder()

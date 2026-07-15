from __future__ import annotations

from structure import available_scene_names, build_scene


class SceneService:
    def available_scene_names(self) -> list[str]:
        return available_scene_names()

    def load_scene(self, scene_name: str):
        return build_scene(scene_name)

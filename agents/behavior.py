from __future__ import annotations


AREA_BEHAVIORS = {
    "entrance_area": "entering",
    "teacher_work_area": "working",
    "lore_display_area": "observing",
    "student_consult_area": "consulting",
    "potion_brewing_area": "brewing",
    "fireplace_area": "resting",
    "cleanup_area": "cleaning",
    "ingredient_storage_area": "searching",
    "living_room": "resting",
    "kitchen": "preparing",
    "bedroom": "resting",
    "bathroom": "cleaning",
    "office_area": "working",
}


def behavior_for_area(area_id: str | None) -> str:
    if area_id is None:
        return "idle"
    return AREA_BEHAVIORS.get(area_id, "interacting")

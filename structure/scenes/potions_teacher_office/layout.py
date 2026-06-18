AREA_DEFINITIONS = [
    ("entrance_area", "入口与衣帽区", (0.20, 0.35, 2.95, 3.25)),
    ("teacher_work_area", "教师办公区", (2.95, 0.35, 6.35, 4.25)),
    ("lore_display_area", "窗边图谱与展示区", (6.35, 0.35, 9.40, 3.20)),
    ("student_consult_area", "学生答疑区", (0.20, 3.25, 3.55, 6.35)),
    ("potion_brewing_area", "魔药调制区", (6.10, 3.20, 9.40, 6.85)),
    ("fireplace_area", "壁炉与炉边区", (0.20, 6.35, 3.35, 9.75)),
    ("cleanup_area", "清洗收尾区", (3.35, 6.35, 6.10, 9.75)),
    ("ingredient_storage_area", "材料储藏区", (6.10, 6.85, 9.40, 9.75)),
]


PORTAL_DEFINITIONS = [
    {
        "id": "office_door_corridor_portal",
        "name": "厚重木门到旧石廊",
        "kind": "door",
        "areas": ("entrance_area", "outside"),
        "segment": ((0.20, 1.00), (0.20, 2.20)),
    },
    {
        "id": "entrance_work_opening",
        "name": "衣帽区到教师办公区通道",
        "kind": "opening",
        "areas": ("entrance_area", "teacher_work_area"),
        "segment": ((2.95, 1.18), (2.95, 2.72)),
    },
    {
        "id": "work_lore_opening",
        "name": "办公区到窗边展示区通道",
        "kind": "opening",
        "areas": ("teacher_work_area", "lore_display_area"),
        "segment": ((6.35, 1.10), (6.35, 2.70)),
    },
    {
        "id": "entrance_consult_opening",
        "name": "入口到答疑区通道",
        "kind": "opening",
        "areas": ("entrance_area", "student_consult_area"),
        "segment": ((0.95, 3.25), (2.70, 3.25)),
    },
    {
        "id": "consult_work_opening",
        "name": "答疑区到办公桌通道",
        "kind": "opening",
        "areas": ("student_consult_area", "teacher_work_area"),
        "segment": ((3.55, 3.45), (3.55, 4.20)),
    },
    {
        "id": "work_brewing_opening",
        "name": "办公区到魔药实验台通道",
        "kind": "opening",
        "areas": ("teacher_work_area", "potion_brewing_area"),
        "segment": ((6.10, 3.42), (6.10, 4.25)),
    },
    {
        "id": "consult_fireplace_opening",
        "name": "答疑区到壁炉区通道",
        "kind": "opening",
        "areas": ("student_consult_area", "fireplace_area"),
        "segment": ((0.95, 6.35), (2.70, 6.35)),
    },
    {
        "id": "fireplace_cleanup_opening",
        "name": "壁炉区到清洗区通道",
        "kind": "opening",
        "areas": ("fireplace_area", "cleanup_area"),
        "segment": ((3.35, 7.00), (3.35, 8.85)),
    },
    {
        "id": "cleanup_ingredient_opening",
        "name": "清洗区到材料储藏区通道",
        "kind": "opening",
        "areas": ("cleanup_area", "ingredient_storage_area"),
        "segment": ((6.10, 7.22), (6.10, 9.15)),
    },
    {
        "id": "brewing_ingredient_opening",
        "name": "魔药实验台到材料柜通道",
        "kind": "opening",
        "areas": ("potion_brewing_area", "ingredient_storage_area"),
        "segment": ((7.10, 6.85), (8.95, 6.85)),
    },
]


POTIONS_TEACHER_OFFICE_DEFAULT_AGENT_START = (1.20, 2.72)  # entrance_area


RENDERING = {
    "area_colors": {
        "entrance_area": "#6f5b47",
        "teacher_work_area": "#8a5f32",
        "lore_display_area": "#4d5f60",
        "student_consult_area": "#4f694f",
        "potion_brewing_area": "#5a6f55",
        "fireplace_area": "#6f3f2a",
        "cleanup_area": "#7d8278",
        "ingredient_storage_area": "#7a6538",
    }
}

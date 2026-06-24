AREA_DEFINITIONS = [
    ("north_west_open_area", "西北室外空地", (0.0, 0.0, 26.0, 26.0)),
    ("north_center_open_area", "北侧中央室外空地", (28.0, 0.0, 54.0, 26.0)),
    ("north_east_open_area", "东北室外空地", (56.0, 0.0, 82.0, 26.0)),
    ("west_vertical_road", "西侧竖向道路", (26.0, 0.0, 28.0, 60.0)),
    ("east_vertical_road", "东侧竖向道路", (54.0, 0.0, 56.0, 60.0)),
    ("central_horizontal_road", "中央横向道路", (0.0, 26.0, 82.0, 30.0)),
    ("home_indoor_region", "Home 室内区域", (0.0, 30.0, 26.0, 60.0)),
    ("office_indoor_region", "Office 室内区域", (28.0, 30.0, 54.0, 60.0)),
    ("potions_teacher_office_indoor_region", "魔药办公室室内区域", (56.0, 30.0, 82.0, 60.0)),
]


AREA_METADATA = {
    "north_west_open_area": {"space": "outdoor", "area_type": "open_lot", "walkable": True},
    "north_center_open_area": {"space": "outdoor", "area_type": "open_lot", "walkable": True},
    "north_east_open_area": {"space": "outdoor", "area_type": "open_lot", "walkable": True},
    "west_vertical_road": {"space": "outdoor", "area_type": "road", "walkable": True},
    "east_vertical_road": {"space": "outdoor", "area_type": "road", "walkable": True},
    "central_horizontal_road": {"space": "outdoor", "area_type": "road", "walkable": True},
    "home_indoor_region": {"space": "outdoor", "area_type": "building_lot", "source_scene": "home", "walkable": True},
    "office_indoor_region": {"space": "outdoor", "area_type": "building_lot", "source_scene": "office", "walkable": True},
    "potions_teacher_office_indoor_region": {
        "space": "outdoor",
        "area_type": "building_lot",
        "source_scene": "potions_teacher_office",
        "walkable": True,
    },
}


PORTAL_DEFINITIONS = [
    {
        "id": "road_to_home_entrance",
        "name": "中央道路到 Home",
        "kind": "building_entrance",
        "areas": ("central_horizontal_road", "home_indoor_region"),
        "segment": ((10.0, 30.0), (16.0, 30.0)),
    },
    {
        "id": "road_to_office_entrance",
        "name": "中央道路到 Office",
        "kind": "building_entrance",
        "areas": ("central_horizontal_road", "office_indoor_region"),
        "segment": ((38.0, 30.0), (44.0, 30.0)),
    },
    {
        "id": "road_to_potions_entrance",
        "name": "中央道路到魔药办公室",
        "kind": "building_entrance",
        "areas": ("central_horizontal_road", "potions_teacher_office_indoor_region"),
        "segment": ((66.0, 30.0), (72.0, 30.0)),
    },
]


COMMUNITY_OUTDOOR_DEFAULT_AGENT_START = (41.0, 28.0)


RENDERING = {
    "area_colors": {
        "north_west_open_area": "#e9d7c2",
        "north_center_open_area": "#eadfcc",
        "north_east_open_area": "#e9d7c2",
        "west_vertical_road": "#a8a8a8",
        "east_vertical_road": "#a8a8a8",
        "central_horizontal_road": "#9c9c9c",
        "home_indoor_region": "#7b9b7b",
        "office_indoor_region": "#7d91a8",
        "potions_teacher_office_indoor_region": "#8d7ba6",
    }
}

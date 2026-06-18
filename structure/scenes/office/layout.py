AREA_DEFINITIONS = [
    ("storage_archive_area", "文件收纳区", (0.20, 0.35, 3.35, 2.55)),
    ("main_workspace", "主办公区", (3.35, 0.35, 7.25, 4.65)),
    ("print_supply_area", "打印与办公用品区", (7.25, 0.35, 9.45, 4.65)),
    ("lounge_area", "休息接待区", (0.20, 2.55, 3.35, 6.20)),
    ("meeting_area", "小型会谈区", (3.35, 4.65, 7.25, 7.15)),
    ("entryway", "办公室玄关 / 入口区", (0.20, 6.20, 2.35, 9.75)),
    ("pantry_area", "茶水区", (3.35, 7.15, 7.25, 9.75)),
    ("bathroom", "卫生间", (7.25, 6.55, 9.45, 9.75)),
]


PORTAL_DEFINITIONS = [
    {
        "id": "office_front_door_portal",
        "name": "办公室入口门",
        "kind": "door",
        "areas": ("entryway", "outside"),
        "segment": ((0.75, 9.75), (1.85, 9.75)),
    },
    {
        "id": "entry_lounge_opening",
        "name": "入口到接待区通道",
        "kind": "opening",
        "areas": ("entryway", "lounge_area"),
        "segment": ((1.05, 6.20), (2.15, 6.20)),
    },
    {
        "id": "lounge_storage_opening",
        "name": "接待区到文件收纳区通道",
        "kind": "opening",
        "areas": ("lounge_area", "storage_archive_area"),
        "segment": ((1.00, 2.55), (2.60, 2.55)),
    },
    {
        "id": "lounge_workspace_opening",
        "name": "接待区到主办公区通道",
        "kind": "opening",
        "areas": ("lounge_area", "main_workspace"),
        "segment": ((3.35, 2.95), (3.35, 4.15)),
    },
    {
        "id": "workspace_print_opening",
        "name": "主办公区到打印区通道",
        "kind": "opening",
        "areas": ("main_workspace", "print_supply_area"),
        "segment": ((7.25, 1.45), (7.25, 3.75)),
    },
    {
        "id": "workspace_meeting_opening",
        "name": "主办公区到会谈区通道",
        "kind": "opening",
        "areas": ("main_workspace", "meeting_area"),
        "segment": ((4.40, 4.65), (6.45, 4.65)),
    },
    {
        "id": "meeting_pantry_opening",
        "name": "会谈区到茶水区通道",
        "kind": "opening",
        "areas": ("meeting_area", "pantry_area"),
        "segment": ((4.10, 7.15), (6.80, 7.15)),
    },
    {
        "id": "pantry_bathroom_opening",
        "name": "茶水区到卫生间通道",
        "kind": "door",
        "areas": ("pantry_area", "bathroom"),
        "segment": ((7.25, 7.35), (7.25, 8.65)),
    },
]


OFFICE_DEFAULT_AGENT_START = (1.30, 8.35)  # entryway


RENDERING = {
    "area_colors": {
        "storage_archive_area": "#d6b98f",
        "main_workspace": "#d8a96f",
        "print_supply_area": "#c6b7a4",
        "lounge_area": "#a8bf8f",
        "meeting_area": "#dbc17b",
        "entryway": "#cfc0b1",
        "pantry_area": "#d3a36d",
        "bathroom": "#8fc4d8",
    }
}

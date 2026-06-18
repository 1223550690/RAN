AREA_DEFINITIONS = [
    ("kitchen", "厨房", (0.20, 0.35, 4.10, 3.60)),
    ("dining_room", "餐厅", (4.10, 0.35, 6.50, 3.75)),
    ("bedroom", "卧室", (6.55, 0.25, 9.15, 4.35)),
    ("entryway", "玄关（含入户外平台）", (0.20, 3.95, 2.25, 9.75)),
    ("living_room", "客厅（含中部过渡区）", (2.25, 3.60, 7.05, 8.55)),
    ("bathroom", "卫生间", (7.05, 4.35, 9.15, 7.25)),
    ("main_balcony", "主阳台", (2.35, 8.55, 7.05, 9.75)),
    ("utility_balcony", "洗衣阳台 / 生活阳台", (7.05, 7.25, 9.15, 9.75)),
]


HOME_DEFAULT_AGENT_START = (3.10, 5.10)  # living_room


RENDERING = {
    "area_colors": {
        "kitchen": "#f1d2a8",
        "dining_room": "#e6d994",
        "bedroom": "#bdd7b4",
        "entryway": "#d8c8bd",
        "living_room": "#e6c89b",
        "bathroom": "#afd6e6",
        "main_balcony": "#bcdab7",
        "utility_balcony": "#b7d8bf",
    }
}


# 门和主要通道采用线段形式定义。
# segment = ((x1, y1), (x2, y2))
# kind:
# - door: 实体门
# - opening: 开放通道
# - glass_door: 玻璃门
PORTAL_DEFINITIONS = [
    {
        "id": "front_door_portal",
        "name": "入户门",
        "kind": "door",
        "areas": ("entryway", "outside"),
        "segment": ((0.20, 7.45), (0.20, 8.45)),
    },
    {
        "id": "entry_living_opening",
        "name": "玄关到客厅通道",
        "kind": "opening",
        "areas": ("entryway", "living_room"),
        "segment": ((2.25, 5.10), (2.25, 8.10)),
    },
    {
        "id": "kitchen_dining_opening",
        "name": "厨房到餐厅通道",
        "kind": "opening",
        "areas": ("kitchen", "dining_room"),
        "segment": ((4.10, 1.60), (4.10, 3.10)),
    },
    {
        "id": "dining_living_opening",
        "name": "餐厅到客厅通道",
        "kind": "opening",
        "areas": ("dining_room", "living_room"),
        "segment": ((4.10, 3.75), (6.40, 3.75)),
    },
    {
        "id": "bedroom_door_portal",
        "name": "卧室门",
        "kind": "door",
        "areas": ("living_room", "bedroom"),
        "segment": ((6.78, 3.68), (6.78, 4.28)),
    },
    {
        "id": "bathroom_door_portal",
        "name": "卫生间门",
        "kind": "door",
        "areas": ("living_room", "bathroom"),
        "segment": ((7.05, 5.00), (7.05, 5.95)),
    },
    {
        "id": "bathroom_utility_opening",
        "name": "卫生间到生活阳台通道",
        "kind": "opening",
        "areas": ("bathroom", "utility_balcony"),
        "segment": ((7.45, 7.25), (8.75, 7.25)),
    },
    {
        "id": "living_main_balcony_glass_door",
        "name": "客厅到主阳台玻璃门",
        "kind": "glass_door",
        "areas": ("living_room", "main_balcony"),
        "segment": ((3.40, 8.55), (5.40, 8.55)),
    },
]

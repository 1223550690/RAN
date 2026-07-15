export const sampleScene = {
  node_id: "potions_teacher_Office",
  name: "Potions Teacher Office",
  default_agent_start: [1.2, 2.72],
  rendering: {
    area_colors: {
      entrance_area: "#6f5b47",
      teacher_work_area: "#8a5f32",
      lore_display_area: "#4d5f60",
      student_consult_area: "#4f694f",
      potion_brewing_area: "#5a6f55",
      fireplace_area: "#6f3f2a",
      cleanup_area: "#7d8278",
      ingredient_storage_area: "#7a6538",
    },
  },
  portals: [
    {
      id: "Office_door_corridor_portal",
      name: "Office Door Corridor Portal",
      kind: "door",
      areas: ["entrance_area", "outside"],
      segment: [[0.2, 1.0], [0.2, 2.2]],
    },
    {
      id: "entrance_work_opening",
      name: "Entrance Work Opening",
      kind: "opening",
      areas: ["entrance_area", "teacher_work_area"],
      segment: [[2.95, 1.18], [2.95, 2.72]],
    },
    {
      id: "work_brewing_opening",
      name: "Work Brewing Opening",
      kind: "opening",
      areas: ["teacher_work_area", "potion_brewing_area"],
      segment: [[6.1, 3.42], [6.1, 4.25]],
    },
    {
      id: "brewing_ingredient_opening",
      name: "Brewing Ingredient Opening",
      kind: "opening",
      areas: ["potion_brewing_area", "ingredient_storage_area"],
      segment: [[7.1, 6.85], [8.95, 6.85]],
    },
  ],
  areas: [
    {
      node_id: "entrance_area",
      name: "Entrance Area",
      bounds: [0.2, 0.35, 2.95, 3.25],
      elements: [
        element("heavy_wooden_door", "Heavy Wooden Door", [0.38, 1.55], [0.34, 1.45], false, true, { door_state: "closed" }),
        element("robe_rack", "Robe Rack", [2.08, 1.42], [0.58, 0.82], false, true, { robe_state: "on_rack" }),
        element("dark_teacher_robe", "Dark Teacher Robe", [2.1, 1.58], [0.42, 0.82], true, false),
        element("walking_stick", "Walking Stick", [1.78, 1.58], [0.12, 0.62], true, false),
        element("entrance_rug", "Entrance Rug", [1.22, 2.48], [1.2, 0.68], false, false),
        element("visitor_note_board", "Visitor Note Board", [2.55, 0.88], [0.48, 0.58], false, false, { visitor_note_state: "unread" }),
      ],
    },
    {
      node_id: "teacher_work_area",
      name: "Teacher Work Area",
      bounds: [2.95, 0.35, 6.35, 4.25],
      elements: [
        element("large_wooden_desk", "Large Wooden Desk", [4.62, 3.08], [2.35, 0.96], false, true, { lesson_plan_state: "draft", homework_state: "ungraded" }),
        element("high_back_chair", "High Back Chair", [4.55, 2.15], [0.72, 0.76], false, true, { chair_state: "empty" }),
        element("desk_lantern", "Desk Lantern", [3.68, 2.85], [0.24, 0.3], true, false, { lantern_state: "off" }),
        element("quill_pen", "Quill Pen", [3.92, 2.7], [0.18, 0.42], true, false),
        element("open_lesson_plan", "Open Lesson Plan", [4.66, 2.82], [0.62, 0.44], true, false),
        element("student_homework_stack", "Student Homework Stack", [5.74, 3.08], [0.42, 0.34], true, false),
      ],
    },
    {
      node_id: "lore_display_area",
      name: "Lore Display Area",
      bounds: [6.35, 0.35, 9.4, 3.2],
      elements: [
        element("gothic_window", "Gothic Window", [6.98, 0.72], [1.05, 0.3], false, true, { window_state: "closed" }),
        element("potion_diagram_frame", "Potion Diagram Frame", [8.52, 0.92], [0.62, 0.72], false, true),
        element("brass_astrolabe", "Brass Astrolabe", [7.56, 2.28], [0.45, 0.45], true, false),
        element("display_potion_bottles", "Display Potion Bottles", [8.05, 2.56], [0.75, 0.3], true, false),
      ],
    },
    {
      node_id: "student_consult_area",
      name: "Student Consult Area",
      bounds: [0.2, 3.25, 3.55, 6.35],
      elements: [
        element("round_consult_table", "Round Consult Table", [1.58, 4.72], [1.1, 1.1], false, true, { consultation_state: "not_started" }),
        element("guest_chair_a", "Guest Chair a", [1.04, 4.05], [0.48, 0.58], false, true),
        element("reference_book", "Reference Book", [1.8, 4.9], [0.36, 0.28], true, false),
        element("tea_cup", "Tea Cup", [1.38, 4.52], [0.16, 0.16], true, false, { tea_state: "empty" }),
      ],
    },
    {
      node_id: "potion_brewing_area",
      name: "Potion Brewing Area",
      bounds: [6.1, 3.2, 9.4, 6.85],
      elements: [
        element("iron_cauldron", "Iron Cauldron", [7.2, 4.62], [0.8, 0.8], false, true, { cauldron_state: "empty", potion_stability: "stable" }),
        element("heating_flame", "Heating Flame", [7.2, 5.1], [0.48, 0.34], false, true, { flame_state: "off" }),
        element("stirring_rod", "Stirring Rod", [7.42, 4.45], [0.12, 0.62], true, false),
        element("curved_brewing_workbench", "Curved Brewing Workbench", [7.72, 5.72], [2.38, 0.8], false, true),
        element("glass_flask", "Glass Flask", [8.28, 4.4], [0.26, 0.34], true, false),
        element("brass_scale", "Brass Scale", [8.82, 5.9], [0.55, 0.36], true, false),
      ],
    },
    {
      node_id: "fireplace_area",
      name: "Fireplace Area",
      bounds: [0.2, 6.35, 3.35, 9.75],
      elements: [
        element("stone_fireplace", "Stone Fireplace", [0.94, 7.54], [1.05, 1.12], false, true, { fireplace_state: "low" }),
        element("firewood_stack", "Firewood Stack", [1.58, 8.62], [0.55, 0.36], true, false),
        element("fireplace_poker", "Fireplace Poker", [1.72, 7.58], [0.12, 0.62], true, false),
        element("ash_bucket", "Ash Bucket", [2.4, 8.72], [0.38, 0.42], false, true),
      ],
    },
    {
      node_id: "cleanup_area",
      name: "Cleanup Area",
      bounds: [3.35, 6.35, 6.1, 9.75],
      elements: [
        element("stone_sink", "Stone Sink", [4.18, 7.32], [0.95, 0.78], false, true, { sink_state: "clean", tap_state: "off" }),
        element("drying_rack", "Drying Rack", [5.12, 7.14], [0.64, 0.42], false, true),
        element("glassware_set_dirty", "Glassware Set Dirty", [4.88, 6.78], [0.46, 0.3], true, false, { glassware_state: "dirty" }),
        element("cleaning_cloth", "Cleaning Cloth", [5.26, 7.58], [0.28, 0.18], true, false),
      ],
    },
    {
      node_id: "ingredient_storage_area",
      name: "Ingredient Storage Area",
      bounds: [6.1, 6.85, 9.4, 9.75],
      elements: [
        element("apothecary_drawer_cabinet", "Apothecary Drawer Cabinet", [7.02, 8.02], [1.1, 1.42], false, true, { inventory_state: "normal" }),
        element("glass_jar_shelf", "Glass Jar Shelf", [8.52, 7.82], [1.08, 1.3], false, true),
        element("rare_ingredient_cabinet", "Rare Ingredient Cabinet", [8.48, 9.08], [0.98, 0.78], false, true, { rare_cabinet_state: "locked" }),
        element("cabinet_key", "Cabinet Key", [6.45, 8.28], [0.14, 0.08], true, false),
        element("inventory_scroll", "Inventory Scroll", [6.75, 8.35], [0.32, 0.18], true, false),
      ],
    },
  ],
};

function element(nodeId, name, center, size, movable, blocksMovement, stateDetails = {}) {
  return {
    node_id: nodeId,
    name,
    center,
    size,
    movable,
    blocks_movement: blocksMovement,
    physical_status: "regular",
    evolution_status: "stable",
    interaction_status: "idle",
    state_details: stateDetails,
  };
}

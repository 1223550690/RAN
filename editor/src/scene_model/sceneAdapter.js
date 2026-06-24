export function cloneScene(scene) {
  return structuredClone(scene);
}

export function normalizeStructureScene(scene) {
  return {
    node_id: scene.node_id || "scene",
    name: scene.name || scene.node_id || "Scene",
    default_agent_start: normalizePoint(scene.default_agent_start),
    portals: Array.isArray(scene.portals) ? scene.portals : [],
    rendering: scene.rendering || { area_colors: {} },
    areas: (scene.areas || []).map((area) => ({
      node_id: area.node_id,
      name: area.name || area.node_id,
      bounds: normalizeBounds(area.bounds),
      metadata: area.metadata || {},
      elements: (area.elements || []).map(normalizeElement),
    })),
  };
}

export function createElement(area, worldPoint) {
  const base = uniqueId(area.elements, "new_element");
  return {
    node_id: base,
    name: "新元素",
    center: [round(worldPoint[0]), round(worldPoint[1])],
    size: [0.55, 0.42],
    movable: true,
    blocks_movement: false,
    physical_status: "regular",
    evolution_status: "stable",
    interaction_status: "idle",
    state_details: {},
  };
}

export function duplicateElement(area, element) {
  const copy = structuredClone(element);
  copy.node_id = uniqueId(area.elements, `${element.node_id}_copy`);
  copy.name = `${element.name} 副本`;
  copy.center = [round(element.center[0] + 0.25), round(element.center[1] + 0.25)];
  return copy;
}

export function findArea(scene, areaId) {
  return scene.areas.find((area) => area.node_id === areaId) || null;
}

export function findAreaAt(scene, point) {
  return scene.areas.find((area) => pointInBounds(point, area.bounds)) || null;
}

export function findElement(scene, elementId) {
  for (const area of scene.areas) {
    const element = area.elements.find((item) => item.node_id === elementId);
    if (element) {
      return { area, element };
    }
  }
  return null;
}

export function deleteElement(scene, elementId) {
  for (const area of scene.areas) {
    const index = area.elements.findIndex((item) => item.node_id === elementId);
    if (index >= 0) {
      area.elements.splice(index, 1);
      return true;
    }
  }
  return false;
}

export function updateElementCenter(scene, elementId, center) {
  const result = findElement(scene, elementId);
  if (!result) return false;
  result.element.center = [round(center[0]), round(center[1])];
  return true;
}

export function pointInBounds(point, bounds) {
  const [x, y] = point;
  const [minX, minY, maxX, maxY] = bounds;
  return x >= minX && x <= maxX && y >= minY && y <= maxY;
}

function normalizeElement(element) {
  return {
    node_id: element.node_id,
    name: element.name || element.node_id,
    center: normalizePoint(element.center),
    size: normalizeSize(element.size),
    movable: Boolean(element.movable),
    blocks_movement: Boolean(element.blocks_movement),
    physical_status: element.physical_status || element.status || "regular",
    evolution_status: element.evolution_status || "stable",
    interaction_status: element.interaction_status || "idle",
    state_details: element.state_details || {},
  };
}

function normalizeBounds(bounds) {
  return Array.isArray(bounds) && bounds.length === 4 ? bounds.map(Number) : [0, 0, 1, 1];
}

function normalizePoint(point) {
  return Array.isArray(point) && point.length === 2 ? point.map(Number) : [0, 0];
}

function normalizeSize(size) {
  return Array.isArray(size) && size.length === 2 ? size.map(Number) : [0.5, 0.5];
}

function uniqueId(items, prefix) {
  const used = new Set(items.map((item) => item.node_id));
  let candidate = prefix;
  let suffix = 1;
  while (used.has(candidate)) {
    candidate = `${prefix}_${suffix}`;
    suffix += 1;
  }
  return candidate;
}

function round(value) {
  return Math.round(Number(value) * 100) / 100;
}

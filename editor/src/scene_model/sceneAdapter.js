export function cloneScene(scene) {
  return structuredClone(scene);
}

export function normalizeStructureScene(scene) {
  return {
    node_id: scene.node_id || "scene",
    name: scene.name || scene.node_id || "Scene",
    metadata: scene.metadata || {},
    default_agent_start: normalizePoint(scene.default_agent_start),
    portals: Array.isArray(scene.portals) ? scene.portals.map(normalizePortal) : [],
    walls: Array.isArray(scene.walls) ? scene.walls.map(normalizeWall) : [],
    roads: normalizeRoads(scene.roads),
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

function normalizePortal(portal) {
  const endpoints = Array.isArray(portal.endpoints) && portal.endpoints.length >= 2
    ? portal.endpoints.slice(0, 2).map(normalizeEndpoint)
    : (Array.isArray(portal.areas) ? portal.areas.slice(0, 2).map((areaId) => ({ object_type: "area", object_id: areaId })) : []);
  return {
    id: portal.id || portal.portal_id,
    name: portal.name || portal.id || portal.portal_id,
    kind: portal.kind || "opening",
    role: portal.role || "passage",
    locked: Boolean(portal.locked),
    areas: Array.isArray(portal.areas) ? portal.areas : endpoints.map((item) => item.object_id),
    endpoints,
    segment: normalizeSegment(portal.segment),
    wall_id: portal.wall_id || null,
    width_m: portal.width_m === undefined ? null : Number(portal.width_m),
    open: portal.open !== false,
  };
}

function normalizeEndpoint(endpoint) {
  return {
    object_type: endpoint.object_type || endpoint.type || "area",
    object_id: endpoint.object_id || endpoint.id || "",
  };
}

function normalizeRoads(roads = {}) {
  return {
    segments: Array.isArray(roads.segments) ? roads.segments.map(normalizeRoadSegment) : [],
    intersections: Array.isArray(roads.intersections) ? roads.intersections.map(normalizeRoadIntersection) : [],
  };
}

function normalizeRoadSegment(road) {
  return {
    road_id: road.road_id || road.id,
    name: road.name || road.road_id || road.id,
    kind: "segment",
    top: normalizeRoadEdge(road.top),
    bottom: normalizeRoadEdge(road.bottom),
    road_type: road.road_type || "pedestrian",
    walkable: road.walkable !== false,
    locked: Boolean(road.locked),
    metadata: road.metadata || {},
  };
}

function normalizeRoadIntersection(intersection) {
  return {
    intersection_id: intersection.intersection_id || intersection.id,
    name: intersection.name || intersection.intersection_id || intersection.id,
    kind: "intersection",
    bounds: normalizeBounds(intersection.bounds),
    connected_roads: Array.isArray(intersection.connected_roads) ? intersection.connected_roads : [],
    road_type: intersection.road_type || "junction",
    walkable: intersection.walkable !== false,
    locked: Boolean(intersection.locked),
    metadata: intersection.metadata || {},
  };
}

function normalizeRoadEdge(edge = {}) {
  return {
    y: Number(edge.y || 0),
    x1: Number(edge.x1 || 0),
    x2: Number(edge.x2 || 0),
  };
}

function normalizeWall(wall) {
  return {
    wall_id: wall.wall_id || wall.id,
    name: wall.name || wall.wall_id || wall.id,
    start: normalizePoint(wall.start),
    end: normalizePoint(wall.end),
    wall_type: wall.wall_type || "interior",
    material: wall.material || "drywall",
    thickness_m: Number(wall.thickness_m || 0.2),
    penetration_loss_db: Number(wall.penetration_loss_db || 5),
    blocks_movement: wall.blocks_movement !== false,
    locked: Boolean(wall.locked),
    areas: Array.isArray(wall.areas) ? wall.areas : [],
    portal_ids: Array.isArray(wall.portal_ids) ? wall.portal_ids : [],
  };
}

export function createRoadSegment(scene) {
  const bounds = scene.rendering?.map_bounds || [0, 0, 100, 100];
  const cx = (bounds[0] + bounds[2]) / 2;
  const cy = (bounds[1] + bounds[3]) / 2;
  const id = uniqueId(scene.roads.segments.map((road) => ({ node_id: road.road_id })), "new_road_segment");
  return {
    road_id: id,
    name: "New road segment",
    kind: "segment",
    top: { y: round(cy - 20), x1: round(cx - 80), x2: round(cx + 80) },
    bottom: { y: round(cy + 20), x1: round(cx - 60), x2: round(cx + 100) },
    road_type: "pedestrian",
    walkable: true,
    locked: false,
    metadata: { space: "outdoor", area_type: "road" },
  };
}

export function createRoadIntersection(scene) {
  const bounds = scene.rendering?.map_bounds || [0, 0, 100, 100];
  const cx = (bounds[0] + bounds[2]) / 2;
  const cy = (bounds[1] + bounds[3]) / 2;
  const id = uniqueId(scene.roads.intersections.map((item) => ({ node_id: item.intersection_id })), "new_road_intersection");
  return {
    intersection_id: id,
    name: "New road intersection",
    kind: "intersection",
    bounds: [round(cx - 20), round(cy - 20), round(cx + 20), round(cy + 20)],
    connected_roads: [],
    road_type: "junction",
    walkable: true,
    locked: false,
    metadata: { space: "outdoor", area_type: "road_intersection" },
  };
}

export function createWall(scene) {
  const bounds = scene.rendering?.map_bounds || [0, 0, 100, 100];
  const cx = (bounds[0] + bounds[2]) / 2;
  const cy = (bounds[1] + bounds[3]) / 2;
  const id = uniqueId(scene.walls.map((wall) => ({ node_id: wall.wall_id })), "new_wall");
  return {
    wall_id: id,
    name: "New wall",
    start: [round(cx - 40), round(cy)],
    end: [round(cx + 40), round(cy)],
    wall_type: "interior",
    material: "drywall",
    thickness_m: 0.2,
    penetration_loss_db: 5,
    blocks_movement: true,
    locked: false,
    areas: [],
    portal_ids: [],
  };
}

export function createPortal(scene, endpoints) {
  const id = uniqueId(scene.portals.map((portal) => ({ node_id: portal.id })), "new_portal");
  const segment = defaultPortalSegment(scene, endpoints);
  return normalizePortal({
    id,
    name: "New portal",
    kind: "open_passage",
    role: "passage",
    endpoints,
    areas: endpoints.map((endpoint) => endpoint.object_id),
    segment,
    locked: false,
    open: true,
  });
}

export function createElement(area, worldPoint) {
  const base = uniqueId(area.elements, "new_element");
  return {
    node_id: base,
    name: "New element",
    center: [round(worldPoint[0]), round(worldPoint[1])],
    size: [50, 50],
    movable: true,
    locked: false,
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
  copy.name = `${element.name} copy`;
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
    movable: element.movable !== false,
    locked: Boolean(element.locked),
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

function normalizeSegment(segment) {
  return Array.isArray(segment) && segment.length === 2
    ? [normalizePoint(segment[0]), normalizePoint(segment[1])]
    : [[0, 0], [1, 0]];
}

function defaultPortalSegment(scene, endpoints) {
  const centers = endpoints.map((endpoint) => objectCenter(scene, endpoint));
  const a = centers[0] || [0, 0];
  const b = centers[1] || [1, 0];
  return [a, b];
}

function objectCenter(scene, endpoint) {
  if (endpoint.object_type === "area") {
    const area = findArea(scene, endpoint.object_id);
    if (!area) return null;
    return [(area.bounds[0] + area.bounds[2]) / 2, (area.bounds[1] + area.bounds[3]) / 2];
  }
  if (endpoint.object_type === "road_segment") {
    const road = scene.roads.segments.find((item) => item.road_id === endpoint.object_id);
    if (!road) return null;
    return [
      (road.top.x1 + road.top.x2 + road.bottom.x1 + road.bottom.x2) / 4,
      (road.top.y + road.bottom.y) / 2,
    ];
  }
  if (endpoint.object_type === "road_intersection") {
    const intersection = scene.roads.intersections.find((item) => item.intersection_id === endpoint.object_id);
    if (!intersection) return null;
    return [
      (intersection.bounds[0] + intersection.bounds[2]) / 2,
      (intersection.bounds[1] + intersection.bounds[3]) / 2,
    ];
  }
  return null;
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
  return Math.round(Number(value));
}

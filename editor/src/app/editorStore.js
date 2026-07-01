import {
  cloneScene,
  createArea,
  createElement,
  createPortal,
  createRoadIntersection,
  createRoadSegment,
  createWall,
  deleteElement,
  duplicateElement,
  findArea,
  findAreaAt,
  findElement,
  normalizeStructureScene,
  updateElementCenter,
} from "../scene_model/sceneAdapter.js";

export class EditorStore {
  constructor(scene) {
    this.scene = normalizeStructureScene(cloneScene(scene));
    this.sceneKey = this.scene.node_id;
    this.hoveredId = null;
    this.selectedId = null;
    this.selectedAreaId = null;
    this.selectedSpatial = null;
    this.listeners = new Set();
    this.undoStack = [];
    this.lastSavedAt = null;
    this.dirty = false;
    this.activeTool = "select";
    this.portalDraft = [];
    this.hoverCoord = null;
    this.parentSceneCache = new Map();
    this.parentScenePathCache = new Map();
    this.scenePath = null;
  }

  subscribe(listener) {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  emit(options = {}) {
    const payload = {
      renderProperties: options.renderProperties ?? false,
      updateHighlights: options.updateHighlights ?? true,
    };
    for (const listener of this.listeners) {
      listener(this.snapshot(), payload);
    }
  }

  snapshot() {
    return {
      scene: this.scene,
      sceneKey: this.sceneKey,
      hoveredId: this.hoveredId,
      selectedId: this.selectedId,
      selectedAreaId: this.selectedAreaId,
      selectedSpatial: this.selectedSpatial,
      dirty: this.dirty,
      lastSavedAt: this.lastSavedAt,
      canUndo: this.undoStack.length > 0,
      activeTool: this.activeTool,
      portalDraft: this.portalDraft,
      hoverCoord: this.hoverCoord,
      scenePath: this.scenePath,
    };
  }

  loadScene(sceneKey, scene, options = {}) {
    this.scene = normalizeStructureScene(cloneScene(scene));
    this.sceneKey = sceneKey;
    this.scenePath = options.scenePath || null;
    this.hoveredId = null;
    this.selectedId = null;
    this.selectedAreaId = null;
    this.selectedSpatial = null;
    this.undoStack = [];
    this.dirty = false;
    this.lastSavedAt = null;
    this.activeTool = "select";
    this.portalDraft = [];
    this.hoverCoord = null;
    this.emit({ renderProperties: true });
  }

  setTool(tool) {
    this.activeTool = this.activeTool === tool ? "select" : tool;
    this.portalDraft = [];
    this.emit({ renderProperties: false });
  }

  setHoverCoord(coord) {
    this.hoverCoord = coord;
    this.emit({ renderProperties: false, updateHighlights: false });
  }

  setHover(id) {
    this.hoveredId = id;
    this.emit({ renderProperties: false });
  }

  setSelected(id) {
    this.selectedId = id;
    this.selectedAreaId = null;
    this.selectedSpatial = null;
    this.emit({ renderProperties: false });
  }

  setSelectedArea(id) {
    this.selectedAreaId = id;
    this.selectedId = null;
    this.selectedSpatial = { type: "area", id };
    this.emit({ renderProperties: false });
  }

  setSelectedSpatial(selection) {
    this.selectedSpatial = selection;
    this.selectedId = null;
    this.selectedAreaId = selection?.type === "area" ? selection.id : null;
    this.emit({ renderProperties: false });
  }

  clearSelection() {
    this.selectedId = null;
    this.selectedAreaId = null;
    this.selectedSpatial = null;
    this.hoveredId = null;
    this.emit({ renderProperties: false });
  }

  updateSceneField(field, value) {
    this.recordChange();
    this.scene[field] = value;
    this.markDirty();
  }

  updateArea(areaId, field, value) {
    const area = findArea(this.scene, areaId);
    if (!area) return;
    this.updateAreaObject(area, field, value);
  }

  updateAreaBounds(areaId, index, value) {
    const area = findArea(this.scene, areaId);
    if (!area) return;
    this.updateAreaBoundsObject(area, index, value);
  }

  updateAreaObject(area, field, value) {
    this.recordChange();
    area[field] = value;
    this.markDirty();
  }

  updateAreaBoundsObject(area, index, value) {
    this.recordChange();
    area.bounds[index] = Number(value);
    this.markDirty();
  }

  updateAreaMetadataObject(area, field, value) {
    this.recordChange();
    area.metadata = area.metadata || {};
    area.metadata[field] = value;
    this.markDirty();
  }

  updateAreaLockedObject(area, value) {
    this.recordChange();
    area.metadata = area.metadata || {};
    area.metadata.locked = Boolean(value);
    this.markDirty();
  }

  updateElement(elementId, field, value) {
    const result = findElement(this.scene, elementId);
    if (!result) return;
    this.updateElementObject(result.element, field, value);
  }

  updateElementVector(elementId, field, index, value) {
    const result = findElement(this.scene, elementId);
    if (!result) return;
    this.updateElementVectorObject(result.element, field, index, value);
  }

  updateElementStateDetails(elementId, jsonText) {
    const result = findElement(this.scene, elementId);
    if (!result) return;
    this.updateElementStateDetailsObject(result.element, jsonText);
  }

  updateElementObject(element, field, value) {
    this.recordChange();
    const oldId = element.node_id;
    element[field] = value;
    if (field === "node_id") {
      if (this.selectedId === oldId) this.selectedId = value;
      if (this.hoveredId === oldId) this.hoveredId = value;
    }
    this.markDirty();
  }

  updateElementVectorObject(element, field, index, value) {
    this.recordChange();
    element[field][index] = Number(value);
    this.markDirty();
  }

  updateElementStateDetailsObject(element, jsonText) {
    try {
      this.recordChange();
      element.state_details = jsonText.trim() ? JSON.parse(jsonText) : {};
      this.markDirty();
    } catch {
      // Keep invalid JSON in the field until the user fixes it.
    }
  }

  beginMove() {
    this.recordChange();
  }

  moveElement(elementId, center) {
    updateElementCenter(this.scene, elementId, center.map(snap));
    this.markDirty({ renderProperties: false });
  }

  resizeElement(elementId, center, size) {
    const result = findElement(this.scene, elementId);
    if (!result) return;
    result.element.center = center.map(snap);
    result.element.size = size.map((value) => Math.max(1, snap(value)));
    this.markDirty({ renderProperties: false });
  }

  addElement(areaId, point = null) {
    const area = findArea(this.scene, areaId);
    if (!area) return null;
    this.recordChange();
    const center = point || [(area.bounds[0] + area.bounds[2]) / 2, (area.bounds[1] + area.bounds[3]) / 2];
    const element = createElement(area, center);
    area.elements.push(element);
    this.selectedId = element.node_id;
    this.selectedAreaId = null;
    this.markDirty({ renderProperties: true });
    return element;
  }

  addElementAt(point) {
    const area = findAreaAt(this.scene, point);
    if (!area) return null;
    return this.addElement(area.node_id, point);
  }

  addArea() {
    this.recordChange();
    const area = createArea(this.scene);
    this.scene.areas.push(area);
    this.selectedAreaId = area.node_id;
    this.selectedId = null;
    this.selectedSpatial = { type: "area", id: area.node_id };
    this.markDirty({ renderProperties: true });
    return area;
  }

  addRoadSegment() {
    this.recordChange();
    const road = createRoadSegment(this.scene);
    this.scene.roads.segments.push(road);
    this.markDirty({ renderProperties: true });
    return road;
  }

  addRoadIntersection() {
    this.recordChange();
    const intersection = createRoadIntersection(this.scene);
    this.scene.roads.intersections.push(intersection);
    this.markDirty({ renderProperties: true });
    return intersection;
  }

  addWall() {
    this.recordChange();
    const wall = createWall(this.scene);
    this.scene.walls.push(wall);
    this.markDirty({ renderProperties: true });
    return wall;
  }

  pickPortalEndpoint(endpoint) {
    if (this.activeTool !== "portal") return;
    if (this.portalDraft.some((item) => item.object_type === endpoint.object_type && item.object_id === endpoint.object_id)) {
      return;
    }
    this.portalDraft = [...this.portalDraft, endpoint];
    if (this.portalDraft.length >= 2) {
      this.recordChange();
      const portal = createPortal(this.scene, this.portalDraft.slice(0, 2));
      this.scene.portals.push(portal);
      this.portalDraft = [];
      this.activeTool = "select";
      this.markDirty({ renderProperties: true });
      return;
    }
    this.emit({ renderProperties: false });
  }

  updatePortalObject(portal, field, value) {
    this.recordChange();
    portal[field] = value;
    if (field === "role") {
      portal.kind = value === "connection" ? "geometry_join" : "open_passage";
    }
    this.markDirty({ renderProperties: true });
  }

  updatePortalSegmentObject(portal, pointIndex, coordIndex, value) {
    this.recordChange();
    portal.segment[pointIndex][coordIndex] = Number(value);
    this.markDirty();
  }

  updateWallObject(wall, field, value) {
    this.recordChange();
    wall[field] = value;
    this.markDirty({ renderProperties: true });
  }

  updateWallPointObject(wall, field, index, value) {
    this.recordChange();
    wall[field][index] = Number(value);
    this.markDirty();
  }

  updateRoadEdgeObject(road, edgeName, field, value) {
    this.recordChange();
    road[edgeName][field] = Number(value);
    this.markDirty();
  }

  updateRoadIntersectionBoundsObject(intersection, index, value) {
    this.recordChange();
    intersection.bounds[index] = Number(value);
    this.markDirty();
  }

  updateRoadObject(road, field, value) {
    this.recordChange();
    road[field] = value;
    this.markDirty();
  }

  updateIntersectionObject(intersection, field, value) {
    this.recordChange();
    intersection[field] = value;
    this.markDirty();
  }

  moveSpatialObject(request) {
    const target = this.findSpatialObject(request.type, request.id);
    if (!target || isLockedSpatial(target)) return;
    applySpatialMove(target, request.delta, request.original);
    this.markDirty({ renderProperties: false });
  }

  resizeSpatialObject(request) {
    const target = this.findSpatialObject(request.type, request.id);
    if (!target || isLockedSpatial(target)) return;
    applySpatialResize(target, request.originalBounds, request.anchor, request.worldPoint, request.original);
    this.markDirty({ renderProperties: false });
  }

  findSpatialObject(type, id) {
    if (type === "area") return this.scene.areas.find((area) => area.node_id === id) || null;
    if (type === "road_segment") return this.scene.roads.segments.find((road) => road.road_id === id) || null;
    if (type === "road_intersection") return this.scene.roads.intersections.find((item) => item.intersection_id === id) || null;
    if (type === "wall") return this.scene.walls.find((wall) => wall.wall_id === id) || null;
    if (type === "portal") return this.scene.portals.find((portal) => portal.id === id) || null;
    return null;
  }

  duplicateElement(elementId) {
    const result = findElement(this.scene, elementId);
    if (!result) return null;
    this.recordChange();
    const copy = duplicateElement(result.area, result.element);
    result.area.elements.push(copy);
    this.selectedId = copy.node_id;
    this.selectedAreaId = null;
    this.markDirty({ renderProperties: true });
    return copy;
  }

  deleteElement(elementId) {
    this.recordChange();
    if (deleteElement(this.scene, elementId)) {
      if (this.selectedId === elementId) this.selectedId = null;
      if (this.hoveredId === elementId) this.hoveredId = null;
      this.markDirty({ renderProperties: true });
    }
  }

  deleteSpatialObject(type, objectId) {
    this.recordChange();
    if (type === "area") {
      this.scene.areas = this.scene.areas.filter((area) => area.node_id !== objectId);
      if (this.selectedAreaId === objectId) this.selectedAreaId = null;
    }
    if (type === "road_segment") {
      this.scene.roads.segments = this.scene.roads.segments.filter((road) => road.road_id !== objectId);
    }
    if (type === "road_intersection") {
      this.scene.roads.intersections = this.scene.roads.intersections.filter((item) => item.intersection_id !== objectId);
    }
    if (type === "wall") {
      this.scene.walls = this.scene.walls.filter((wall) => wall.wall_id !== objectId);
      this.scene.portals = this.scene.portals.map((portal) => (
        portal.wall_id === objectId ? { ...portal, wall_id: null } : portal
      ));
    }
    if (type === "portal") {
      this.scene.portals = this.scene.portals.filter((portal) => portal.id !== objectId);
      this.scene.walls = this.scene.walls.map((wall) => ({
        ...wall,
        portal_ids: (wall.portal_ids || []).filter((portalId) => portalId !== objectId),
      }));
    } else {
      this.scene.portals = this.scene.portals.filter((portal) => (
        !(portal.endpoints || []).some((endpoint) => endpoint.object_type === type && endpoint.object_id === objectId)
      ));
    }
    this.scene.walls = this.scene.walls.map((wall) => ({
      ...wall,
      areas: type === "area" ? (wall.areas || []).map((areaId) => (areaId === objectId ? null : areaId)) : wall.areas,
    }));
    if (this.selectedSpatial?.type === type && this.selectedSpatial.id === objectId) {
      this.selectedSpatial = null;
    }
    this.markDirty({ renderProperties: true });
  }

  openAreaScene(area) {
    if (this.scene.metadata?.editor_child_scene) {
      this.returnToParentScene();
      return;
    }
    const linkedScene = area.metadata?.linked_scene || area.metadata?.source_scene;
    const option = linkedScene ? document.querySelector(`#sceneSelect option[value="${CSS.escape(linkedScene)}"]`) : null;
    if (option && linkedScene) {
      option.selected = true;
      document.querySelector("#sceneSelect")?.dispatchEvent(new Event("change"));
      return;
    }
    const generatedKey = `${this.sceneKey}:${area.node_id}`;
    this.parentSceneCache.set(this.sceneKey, cloneScene(this.scene));
    this.parentScenePathCache.set(this.sceneKey, this.scenePath);
    const generatedScene = createAreaScene(area, this.sceneKey, this.scenePath);
    const select = document.querySelector("#sceneSelect");
    this.removeTemporarySceneOptions(select);
    if (select && !select.querySelector(`option[value="${CSS.escape(generatedKey)}"]`)) {
      const generatedOption = document.createElement("option");
      generatedOption.value = generatedKey;
      generatedOption.textContent = `${generatedKey} / ${area.name}`;
      generatedOption.dataset.temporary = "true";
      generatedOption.dataset.parentKey = this.sceneKey;
      select.append(generatedOption);
      generatedOption.selected = true;
    }
    this.loadScene(generatedKey, generatedScene, { useSaved: false });
  }

  undo() {
    const previous = this.undoStack.pop();
    if (!previous) return;
    this.scene = normalizeStructureScene(previous.scene);
    this.selectedId = previous.selectedId;
    this.selectedAreaId = previous.selectedAreaId || null;
    this.selectedSpatial = previous.selectedSpatial || null;
    this.hoveredId = null;
    this.dirty = true;
    this.emit({ renderProperties: true });
  }

  async save() {
    const time = new Date().toISOString();
    if (this.scene.metadata?.editor_child_scene) {
      const parentScene = this.syncChildSceneToParent();
      if (!parentScene) {
        throw new Error("Parent scene is unavailable.");
      }
      await this.writeSceneFile(this.scene.metadata.parent_scene_key, parentScene, this.scene.metadata.parent_scene_path);
      this.lastSavedAt = time;
      this.dirty = false;
      this.emit({ renderProperties: false });
      return;
    }
    await this.writeSceneFile(this.sceneKey, this.scene, this.scenePath);
    this.parentSceneCache.set(this.sceneKey, cloneScene(this.scene));
    this.parentScenePathCache.set(this.sceneKey, this.scenePath);
    this.lastSavedAt = time;
    this.dirty = false;
    this.emit({ renderProperties: false });
  }

  returnToParentScene() {
    if (!this.scene.metadata?.editor_child_scene) return;
    const parentKey = this.scene.metadata.parent_scene_key;
    if (!parentKey) return;
    const parentSource = this.parentSceneCache.get(parentKey);
    if (!parentSource) return;
    const select = document.querySelector("#sceneSelect");
    this.removeTemporarySceneOptions(select);
    const parentOption = select?.querySelector(`option[value="${CSS.escape(parentKey)}"]`);
    if (parentOption) parentOption.selected = true;
    this.loadScene(parentKey, parentSource, { scenePath: this.parentScenePathCache.get(parentKey) });
  }

  syncChildSceneToParent() {
    if (!this.scene.metadata?.editor_child_scene) return;
    const parentKey = this.scene.metadata.parent_scene_key;
    const parentAreaId = this.scene.metadata.parent_area_id;
    if (!parentKey || !parentAreaId) return;
    const parentSource = this.parentSceneCache.get(parentKey);
    if (!parentSource) return;
    const parentScene = normalizeStructureScene(cloneScene(parentSource));
    const parentArea = findArea(parentScene, parentAreaId);
    if (!parentArea) return;
    parentArea.areas = this.scene.areas
      .filter((area) => area.metadata?.source !== "auto_open_space")
      .map((area) => cloneScene(area));
    const openSpaceArea = this.scene.areas.find((area) => area.metadata?.source === "auto_open_space");
    const childBounds = this.scene.rendering?.map_bounds || [
      0,
      0,
      parentArea.bounds[2] - parentArea.bounds[0],
      parentArea.bounds[3] - parentArea.bounds[1],
    ];
    parentArea.elements = openSpaceArea
      ? openSpaceArea.elements.map((element) => mapChildElementToParent(element, childBounds, parentArea.bounds))
      : [];
    parentArea.walls = (this.scene.walls || []).map((wall) => cloneScene(wall));
    parentArea.portals = (this.scene.portals || []).map((portal) => cloneScene(portal));
    parentArea.rendering = cloneScene(this.scene.rendering || {});
    this.parentSceneCache.set(parentKey, parentScene);
    this.parentScenePathCache.set(parentKey, this.scene.metadata.parent_scene_path);
    return parentScene;
  }

  exportJson() {
    return JSON.stringify(this.scene, null, 2);
  }

  async writeSceneFile(sceneKey, scene, scenePath) {
    if (!scenePath) {
      throw new Error(`Scene ${sceneKey} has no writable file path.`);
    }
    const response = await fetch("/api/scenes/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        scene_id: sceneKey,
        path: scenePath,
        scene,
      }),
    });
    if (!response.ok) {
      const detail = await response.text();
      throw new Error(detail || `Save failed with HTTP ${response.status}`);
    }
  }

  recordChange(options = {}) {
    this.undoStack.push({
      scene: cloneScene(this.scene),
      selectedId: this.selectedId,
      selectedAreaId: this.selectedAreaId,
      selectedSpatial: this.selectedSpatial,
    });
    if (this.undoStack.length > 80) {
      this.undoStack.shift();
    }
  }

  markDirty(options = {}) {
    this.dirty = true;
    this.emit(options);
  }

  removeTemporarySceneOptions(select) {
    if (!select) return;
    select.querySelectorAll('option[data-temporary="true"]').forEach((option) => option.remove());
  }
}

function snap(value) {
  return Math.round(Number(value));
}

function snapDelta(delta) {
  return delta.map(snap);
}

function isLockedSpatial(object) {
  return Boolean(object.locked || object.metadata?.locked);
}

function applySpatialMove(object, delta, original = object) {
  const [dx, dy] = snapDelta(delta);
  if (Array.isArray(original.bounds)) {
    object.bounds = [original.bounds[0] + dx, original.bounds[1] + dy, original.bounds[2] + dx, original.bounds[3] + dy];
  } else if (original.top && original.bottom) {
    object.top.x1 = original.top.x1 + dx;
    object.top.x2 = original.top.x2 + dx;
    object.top.y = original.top.y + dy;
    object.bottom.x1 = original.bottom.x1 + dx;
    object.bottom.x2 = original.bottom.x2 + dx;
    object.bottom.y = original.bottom.y + dy;
  } else if (original.start && original.end) {
    object.start = [original.start[0] + dx, original.start[1] + dy];
    object.end = [original.end[0] + dx, original.end[1] + dy];
  } else if (original.segment) {
    object.segment = original.segment.map((point) => [point[0] + dx, point[1] + dy]);
  }
}

function applySpatialResize(object, originalBounds, anchor, worldPoint, original = object) {
  const [minX, minY, maxX, maxY] = originalBounds;
  const nextMinX = Math.min(anchor[0], worldPoint[0]);
  const nextMaxX = Math.max(anchor[0], worldPoint[0]);
  const nextMinY = Math.min(anchor[1], worldPoint[1]);
  const nextMaxY = Math.max(anchor[1], worldPoint[1]);
  const nextBounds = [snap(nextMinX), snap(nextMinY), snap(nextMaxX), snap(nextMaxY)];
  const oldWidth = Math.max(1, maxX - minX);
  const oldHeight = Math.max(1, maxY - minY);
  const scaleX = (nextBounds[2] - nextBounds[0]) / oldWidth;
  const scaleY = (nextBounds[3] - nextBounds[1]) / oldHeight;

  const mapPoint = (point) => [
    snap(nextBounds[0] + (point[0] - minX) * scaleX),
    snap(nextBounds[1] + (point[1] - minY) * scaleY),
  ];

  if (Array.isArray(original.bounds)) {
    object.bounds = nextBounds;
  } else if (original.top && original.bottom) {
    const p1 = mapPoint([original.top.x1, original.top.y]);
    const p2 = mapPoint([original.top.x2, original.top.y]);
    const p3 = mapPoint([original.bottom.x1, original.bottom.y]);
    const p4 = mapPoint([original.bottom.x2, original.bottom.y]);
    object.top = { y: p1[1], x1: p1[0], x2: p2[0] };
    object.bottom = { y: p3[1], x1: p3[0], x2: p4[0] };
  } else if (original.start && original.end) {
    object.start = mapPoint(original.start);
    object.end = mapPoint(original.end);
  } else if (original.segment) {
    object.segment = original.segment.map(mapPoint);
  }
}

function mapChildElementToParent(element, childBounds, parentBounds) {
  const childWidth = Math.max(1, childBounds[2] - childBounds[0]);
  const childHeight = Math.max(1, childBounds[3] - childBounds[1]);
  const parentWidth = parentBounds[2] - parentBounds[0];
  const parentHeight = parentBounds[3] - parentBounds[1];
  const scaleX = parentWidth / childWidth;
  const scaleY = parentHeight / childHeight;
  return {
    ...cloneScene(element),
    center: [
      snap(parentBounds[0] + (element.center[0] - childBounds[0]) * scaleX),
      snap(parentBounds[1] + (element.center[1] - childBounds[1]) * scaleY),
    ],
    size: [
      Math.max(1, snap(element.size[0] * scaleX)),
      Math.max(1, snap(element.size[1] * scaleY)),
    ],
  };
}

function mapParentElementToChild(element, parentBounds, childBounds) {
  const parentWidth = Math.max(1, parentBounds[2] - parentBounds[0]);
  const parentHeight = Math.max(1, parentBounds[3] - parentBounds[1]);
  const childWidth = childBounds[2] - childBounds[0];
  const childHeight = childBounds[3] - childBounds[1];
  const scaleX = childWidth / parentWidth;
  const scaleY = childHeight / parentHeight;
  return {
    ...cloneScene(element),
    center: [
      snap(childBounds[0] + (element.center[0] - parentBounds[0]) * scaleX),
      snap(childBounds[1] + (element.center[1] - parentBounds[1]) * scaleY),
    ],
    size: [
      Math.max(1, snap(element.size[0] * scaleX)),
      Math.max(1, snap(element.size[1] * scaleY)),
    ],
  };
}

function createAreaScene(area, parentSceneKey, parentScenePath) {
  const width = Math.max(1, Math.round(area.bounds[2] - area.bounds[0]));
  const height = Math.max(1, Math.round(area.bounds[3] - area.bounds[1]));
  const childBounds = [0, 0, width, height];
  const openAreaId = `${area.node_id}_open_space`;
  const childAreas = [
    {
      node_id: openAreaId,
      name: `${area.name} open space`,
      bounds: childBounds,
      metadata: {
        space: "indoor",
        area_type: "open_space",
        parent_area_id: area.node_id,
        source: "auto_open_space",
        locked: true,
      },
      elements: (area.elements || []).map((element) => mapParentElementToChild(element, area.bounds, childBounds)),
      areas: [],
      portals: [],
      walls: [],
      rendering: {},
    },
    ...(area.areas || []).map((childArea) => cloneScene(childArea)),
  ];
  return {
    node_id: area.node_id,
    name: area.name,
    metadata: {
      editor_child_scene: true,
      parent_scene_key: parentSceneKey,
      parent_scene_path: parentScenePath,
      parent_area_id: area.node_id,
      parent_area_bounds: area.bounds.slice(),
    },
    default_agent_start: [Math.round(width / 2), Math.round(height / 2)],
    portals: [],
    walls: [],
    roads: { segments: [], intersections: [] },
    rendering: {
      map_bounds: childBounds,
      ...(area.rendering || {}),
      area_colors: {
        [openAreaId]: "#eadb96",
        ...(area.rendering?.area_colors || {}),
      },
    },
    areas: childAreas,
    portals: (area.portals || []).map((portal) => cloneScene(portal)),
    walls: (area.walls || []).map((wall) => cloneScene(wall)),
  };
}

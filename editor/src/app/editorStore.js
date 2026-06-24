import {
  cloneScene,
  createElement,
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
    this.listeners = new Set();
    this.undoStack = [];
    this.lastSavedAt = null;
    this.dirty = false;
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
      dirty: this.dirty,
      lastSavedAt: this.lastSavedAt,
      canUndo: this.undoStack.length > 0,
    };
  }

  loadScene(sceneKey, scene) {
    const saved = this.loadSavedScene(sceneKey);
    this.scene = normalizeStructureScene(cloneScene(saved || scene));
    this.sceneKey = sceneKey;
    this.hoveredId = null;
    this.selectedId = null;
    this.selectedAreaId = null;
    this.undoStack = [];
    this.dirty = false;
    this.lastSavedAt = this.loadSavedTime(sceneKey);
    this.emit({ renderProperties: true });
  }

  setHover(id) {
    this.hoveredId = id;
    this.emit({ renderProperties: false });
  }

  setSelected(id) {
    this.selectedId = id;
    this.selectedAreaId = null;
    this.emit({ renderProperties: false });
  }

  setSelectedArea(id) {
    this.selectedAreaId = id;
    this.selectedId = null;
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
    updateElementCenter(this.scene, elementId, center);
    this.markDirty({ renderProperties: false });
  }

  resizeElement(elementId, center, size) {
    const result = findElement(this.scene, elementId);
    if (!result) return;
    result.element.center = center;
    result.element.size = size;
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

  undo() {
    const previous = this.undoStack.pop();
    if (!previous) return;
    this.scene = normalizeStructureScene(previous.scene);
    this.selectedId = previous.selectedId;
    this.selectedAreaId = previous.selectedAreaId || null;
    this.hoveredId = null;
    this.dirty = true;
    this.emit({ renderProperties: true });
  }

  save() {
    const key = this.storageKey(this.sceneKey);
    const time = new Date().toISOString();
    localStorage.setItem(key, this.exportJson());
    localStorage.setItem(`${key}:savedAt`, time);
    this.lastSavedAt = time;
    this.dirty = false;
    this.emit({ renderProperties: false });
  }

  exportJson() {
    return JSON.stringify(this.scene, null, 2);
  }

  recordChange(options = {}) {
    this.undoStack.push({
      scene: cloneScene(this.scene),
      selectedId: this.selectedId,
      selectedAreaId: this.selectedAreaId,
    });
    if (this.undoStack.length > 80) {
      this.undoStack.shift();
    }
  }

  markDirty(options = {}) {
    this.dirty = true;
    this.emit(options);
  }

  storageKey(sceneKey) {
    return `ran-editor:${sceneKey}`;
  }

  loadSavedScene(sceneKey) {
    const saved = localStorage.getItem(this.storageKey(sceneKey));
    if (!saved) return null;
    try {
      return JSON.parse(saved);
    } catch {
      return null;
    }
  }

  loadSavedTime(sceneKey) {
    return localStorage.getItem(`${this.storageKey(sceneKey)}:savedAt`);
  }
}

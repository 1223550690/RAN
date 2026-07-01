import { createTransform, getSceneBounds, hitTestElement, hitTestSpatialObject, roadPolygon, spatialObjectBounds } from "./geometry.js";

export class ScenePreview {
  constructor(canvas, options = {}) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.options = options;
    this.scene = null;
    this.hoveredId = null;
    this.selectedId = null;
    this.selectedAreaId = null;
    this.selectedSpatial = null;
    this.agents = [];
    this.signalMap = null;
    this.qosResults = null;
    this.highlightMode = "none";
    this.buildingOverlayVisible = false;
    this.activeTool = "select";
    this.drag = null;
    this.pan = null;
    this.transform = null;
    this.view = { scaleMultiplier: 1, panX: 0, panY: 0 };
    this.handleSize = 8;

    this.bindEvents();
    this.resize();
  }

  setScene(scene) {
    this.scene = scene;
    this.render();
  }

  setHovered(id) {
    this.hoveredId = id;
    this.render();
  }

  setSelected(id) {
    this.selectedId = id;
    this.render();
  }

  setSelectedArea(id) {
    this.selectedAreaId = id;
    this.render();
  }

  setSelectedSpatial(selection) {
    this.selectedSpatial = selection;
    this.render();
  }

  setAgents(agentStates = []) {
    this.agents = agentStates;
    this.render();
  }

  setSignalMap(signalMap) {
    this.signalMap = signalMap;
    this.render();
  }

  setQosResults(qosResults) {
    this.qosResults = qosResults;
    this.render();
  }

  setHighlightMode(mode) {
    this.highlightMode = mode || "none";
    this.render();
  }

  setBuildingOverlayVisible(visible) {
    this.buildingOverlayVisible = Boolean(visible);
    this.render();
  }

  setActiveTool(tool) {
    this.activeTool = tool || "select";
    this.render();
  }

  fitView() {
    this.view = { scaleMultiplier: 1, panX: 0, panY: 0 };
    this.render();
  }

  resize() {
    const rect = this.canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    this.canvas.width = Math.max(1, Math.floor(rect.width * dpr));
    this.canvas.height = Math.max(1, Math.floor(rect.height * dpr));
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    this.render();
  }

  isInsideSceneBounds(world) {
    const bounds = getSceneBounds(this.scene);
    return world[0] >= bounds[0] && world[0] <= bounds[2] && world[1] >= bounds[1] && world[1] <= bounds[3];
  }

  render() {
    const rect = this.canvas.getBoundingClientRect();
    this.ctx.clearRect(0, 0, rect.width, rect.height);
    this.drawBackground(rect.width, rect.height);

    if (!this.scene) {
      return;
    }

    this.transform = createTransform(getSceneBounds(this.scene), rect.width, rect.height, 42, this.view);
    this.drawMapFrame();
    this.withMapClip(() => {
      this.drawGrid(rect.width, rect.height);
      this.drawAreas();
      this.drawBuildingAreaOverlays();
      this.drawRoads();
      this.drawWalls();
      this.drawPortals();
      this.drawElements();
      this.drawSelectedSpatialHandles();
      this.drawAgentOverlay();
      this.drawSignalOverlay();
      this.drawQosOverlay();
    });
  }

  bindEvents() {
    window.addEventListener("resize", () => this.resize());

    this.canvas.addEventListener("mousemove", (event) => {
      if (!this.scene || !this.transform) return;
      const world = this.eventToWorld(event);
      const hoveredOverlay = this.buildingOverlayAt(world);
      this.options.onCoordinate?.({
        x: Math.floor(world[0]),
        y: Math.floor(world[1]),
      });

      if (this.drag) {
        if (this.drag.kind === "spatial" && this.drag.mode === "resize") {
          this.options.onSpatialResized?.(this.resizeSpatialRequest(this.drag, world));
        } else if (this.drag.kind === "spatial") {
          this.options.onSpatialMoved?.(this.moveSpatialRequest(this.drag, world));
        } else if (this.drag.mode === "resize") {
          this.options.onElementResized?.(this.resizeRequest(this.drag, world));
        } else {
          this.options.onElementMoved?.({ elementId: this.drag.element.node_id, center: world });
        }
        return;
      }

      if (this.pan) {
        const local = this.eventToLocal(event);
        this.view.panX = this.pan.startPanX + local[0] - this.pan.start[0];
        this.view.panY = this.pan.startPanY + local[1] - this.pan.start[1];
        this.render();
        return;
      }

      const local = this.eventToLocal(event);
      const handle = this.resizeHandleAt(local);
      const hit = hitTestElement(this.scene, world);
      const spatialHit = hit ? null : hitTestSpatialObject(this.scene, world);
      const overlayHit = hit ? null : hoveredOverlay;
      const hoveredId = hit?.element.node_id || null;
      if (hit?.element) {
        this.canvas.title = `${hit.element.name} (${hit.element.node_id})`;
      } else if (overlayHit) {
        this.canvas.title = overlayTitle(overlayHit);
      } else {
        this.canvas.title = spatialHit ? `${objectLabel(spatialHit.object)} (${spatialHit.objectId})` : "";
      }
      if (hoveredId !== this.hoveredId) {
        this.options.onHover?.(hoveredId);
      }
      this.canvas.style.cursor = handle?.cursor || (this.canMoveHit(hit) || this.canMoveSpatialHit(spatialHit) ? "move" : "default");
    });

    this.canvas.addEventListener("mouseleave", () => {
      if (!this.drag) {
        this.options.onHover?.(null);
      }
      this.canvas.title = "";
    });

    this.canvas.addEventListener("mousedown", (event) => {
      if (!this.scene || !this.transform) return;
      if (event.button === 1 || (event.button === 0 && event.altKey)) {
        const local = this.eventToLocal(event);
        this.pan = {
          start: local,
          startPanX: this.view.panX,
          startPanY: this.view.panY,
        };
        return;
      }
      if (event.button !== 0) return;
      const local = this.eventToLocal(event);
      const world = this.eventToWorld(event);
      if (!this.isInsideSceneBounds(world)) {
        this.options.onClearSelection?.();
        return;
      }
      if (this.activeTool === "portal") {
        const spatialHit = hitTestSpatialObject(this.scene, world);
        if (spatialHit) {
          this.options.onSpatialPick?.({
            object_type: spatialHit.type,
            object_id: spatialHit.objectId,
          });
        }
        return;
      }
      const handle = this.resizeHandleAt(local);
      if (handle) {
        this.options.onMoveStart?.({});
        this.drag = {
          mode: "resize",
          kind: handle.kind || "element",
          element: handle.element,
          spatial: handle.spatial,
          corner: handle.corner,
          anchor: handle.anchor,
          originalBounds: handle.originalBounds,
        };
        return;
      }
      const hit = hitTestElement(this.scene, world);
      const wasSelected = hit?.element?.node_id === this.selectedId;
      if (hit?.element) {
        this.options.onSelect?.(hit.element.node_id);
      } else {
        const spatialHit = hitTestSpatialObject(this.scene, world);
        if (spatialHit) {
          this.options.onSpatialSelect?.({ type: spatialHit.type, id: spatialHit.objectId });
        }
      }
      if (wasSelected && this.canMoveHit(hit)) {
        this.options.onMoveStart?.({ elementId: hit.element.node_id });
        this.drag = { mode: "move", ...hit };
        return;
      }
      const spatialHit = hit ? null : hitTestSpatialObject(this.scene, world);
      if (this.canMoveSpatialHit(spatialHit)) {
        this.options.onMoveStart?.({});
        this.drag = {
          mode: "move",
          kind: "spatial",
          spatial: spatialHit,
          startWorld: world,
          original: structuredClone(spatialHit.object),
        };
      }
    });

    window.addEventListener("mouseup", () => {
      this.drag = null;
      this.pan = null;
    });

    this.canvas.addEventListener("wheel", (event) => {
      if (!this.scene || !this.transform) return;
      event.preventDefault();
      const local = this.eventToLocal(event);
      const before = this.transform.toWorld(local);
      const factor = event.deltaY < 0 ? 1.12 : 0.88;
      this.view.scaleMultiplier = Math.min(40, Math.max(0.08, this.view.scaleMultiplier * factor));
      this.render();
      const after = this.transform.toScreen(before);
      this.view.panX += local[0] - after[0];
      this.view.panY += local[1] - after[1];
      this.render();
    }, { passive: false });

    this.canvas.addEventListener("contextmenu", (event) => {
      event.preventDefault();
      if (!this.scene || !this.transform) return;
      const world = this.eventToWorld(event);
      const hit = hitTestElement(this.scene, world);
      const spatialHit = hitTestSpatialObject(this.scene, world);
      this.options.onContextMenu?.({
        client: [event.clientX, event.clientY],
        local: this.eventToLocal(event),
        world,
        target: hit || spatialHit,
      });
    });
  }

  eventToLocal(event) {
    const rect = this.canvas.getBoundingClientRect();
    return [event.clientX - rect.left, event.clientY - rect.top];
  }

  eventToWorld(event) {
    return this.transform.toWorld(this.eventToLocal(event));
  }

  canMoveHit(hit) {
    return hit?.element && !hit.element.locked && hit.element.node_id === this.selectedId;
  }

  canMoveSpatialHit(hit) {
    return hit
      && !isObjectLocked(hit.object)
      && this.selectedSpatial?.type === hit.type
      && this.selectedSpatial?.id === hit.objectId;
  }

  selectedMovableElement() {
    if (!this.selectedId) return null;
    for (const area of this.scene?.areas || []) {
      const element = area.elements.find((item) => item.node_id === this.selectedId);
      if (element && !element.locked) return element;
    }
    return null;
  }

  resizeHandleAt(localPoint) {
    const element = this.selectedMovableElement();
    if (!this.transform) return null;
    let rect = null;
    let payload = null;
    if (element) {
      rect = this.transform.elementToScreen(element);
      payload = { kind: "element", element };
    } else {
      const spatial = this.selectedSpatialHit();
      const bounds = spatialObjectBounds(spatial);
      if (!spatial || isObjectLocked(spatial.object) || !bounds) return null;
      rect = this.transform.rectToScreen(bounds);
      payload = { kind: "spatial", spatial, originalBounds: bounds };
    }
    const [x, y, width, height] = rect;
    let bounds = null;
    if (element) {
      bounds = [
        element.center[0] - element.size[0] / 2,
        element.center[1] - element.size[1] / 2,
        element.center[0] + element.size[0] / 2,
        element.center[1] + element.size[1] / 2,
      ];
    } else {
      bounds = payload.originalBounds;
    }
    const [minX, minY, maxX, maxY] = bounds;
    const handles = [
      { corner: "nw", cursor: "nwse-resize", point: [x, y], anchor: [maxX, maxY] },
      { corner: "ne", cursor: "nesw-resize", point: [x + width, y], anchor: [minX, maxY] },
      { corner: "sw", cursor: "nesw-resize", point: [x, y + height], anchor: [maxX, minY] },
      { corner: "se", cursor: "nwse-resize", point: [x + width, y + height], anchor: [minX, minY] },
    ];
    const half = this.handleSize / 2;
    const found = handles.find((handle) => (
      localPoint[0] >= handle.point[0] - half
      && localPoint[0] <= handle.point[0] + half
      && localPoint[1] >= handle.point[1] - half
      && localPoint[1] <= handle.point[1] + half
    ));
    return found ? { ...found, ...payload } : null;
  }

  selectedSpatialHit() {
    if (!this.selectedSpatial || !this.scene) return null;
    const { type, id } = this.selectedSpatial;
    if (type === "area") {
      const object = this.scene.areas.find((area) => area.node_id === id);
      return object ? { type, object, objectId: id } : null;
    }
    if (type === "road_segment") {
      const object = this.scene.roads?.segments.find((road) => road.road_id === id);
      return object ? { type, object, objectId: id } : null;
    }
    if (type === "road_intersection") {
      const object = this.scene.roads?.intersections.find((item) => item.intersection_id === id);
      return object ? { type, object, objectId: id } : null;
    }
    if (type === "wall") {
      const object = this.scene.walls.find((wall) => wall.wall_id === id);
      return object ? { type, object, objectId: id } : null;
    }
    if (type === "portal") {
      const object = this.scene.portals.find((portal) => portal.id === id);
      return object ? { type, object, objectId: id } : null;
    }
    return null;
  }

  resizeRequest(drag, worldPoint) {
    const minSize = 0.2;
    const width = Math.max(minSize, Math.abs(worldPoint[0] - drag.anchor[0]));
    const height = Math.max(minSize, Math.abs(worldPoint[1] - drag.anchor[1]));
    return {
      elementId: drag.element.node_id,
      center: [(worldPoint[0] + drag.anchor[0]) / 2, (worldPoint[1] + drag.anchor[1]) / 2],
      size: [width, height],
    };
  }

  moveSpatialRequest(drag, worldPoint) {
    return {
      type: drag.spatial.type,
      id: drag.spatial.objectId,
      delta: [worldPoint[0] - drag.startWorld[0], worldPoint[1] - drag.startWorld[1]],
      original: drag.original,
    };
  }

  resizeSpatialRequest(drag, worldPoint) {
    return {
      type: drag.spatial.type,
      id: drag.spatial.objectId,
      anchor: drag.anchor,
      worldPoint,
      originalBounds: drag.originalBounds,
      original: structuredClone(drag.spatial.object),
    };
  }

  drawBackground(width, height) {
    this.ctx.fillStyle = "#ffffff";
    this.ctx.fillRect(0, 0, width, height);
  }

  drawMapFrame() {
    const bounds = this.scene?.rendering?.map_bounds;
    if (!Array.isArray(bounds) || bounds.length !== 4) return;
    const [x, y, width, height] = this.transform.rectToScreen(bounds);
    this.ctx.save();
    this.ctx.fillStyle = "#ffffff";
    this.ctx.fillRect(x, y, width, height);
    this.ctx.strokeStyle = "rgb(0 0 0 / 18%)";
    this.ctx.lineWidth = 1;
    this.ctx.strokeRect(x, y, width, height);
    this.ctx.restore();
  }

  withMapClip(draw) {
    const bounds = this.scene?.rendering?.map_bounds;
    if (!Array.isArray(bounds) || bounds.length !== 4) {
      draw();
      return;
    }
    const [x, y, width, height] = this.transform.rectToScreen(bounds);
    this.ctx.save();
    this.ctx.beginPath();
    this.ctx.rect(x, y, width, height);
    this.ctx.clip();
    draw();
    this.ctx.restore();
  }

  drawGrid(width, height) {
    if (!this.transform || !this.scene) return;
    const sceneBounds = getSceneBounds(this.scene);
    this.ctx.save();
    this.ctx.strokeStyle = "rgb(120 120 120 / 10%)";
    this.ctx.lineWidth = 1;
    const minX = Math.floor(sceneBounds[0]);
    const minY = Math.floor(sceneBounds[1]);
    const maxX = Math.ceil(sceneBounds[2]);
    const maxY = Math.ceil(sceneBounds[3]);
    for (let worldX = minX; worldX <= maxX; worldX += 1) {
      const [x] = this.transform.toScreen([worldX, minY]);
      if (x < -1 || x > width + 1) continue;
      this.ctx.beginPath();
      this.ctx.moveTo(x, 0);
      this.ctx.lineTo(x, height);
      this.ctx.stroke();
    }
    for (let worldY = minY; worldY <= maxY; worldY += 1) {
      const [, y] = this.transform.toScreen([minX, worldY]);
      if (y < -1 || y > height + 1) continue;
      this.ctx.beginPath();
      this.ctx.moveTo(0, y);
      this.ctx.lineTo(width, y);
      this.ctx.stroke();
    }
    this.ctx.restore();
  }

  drawAreas() {
    for (const area of this.scene.areas) {
      const [x, y, width, height] = this.transform.rectToScreen(area.bounds);
      const fill = this.scene.rendering?.area_colors?.[area.node_id] || "#7d8278";
      const highlight = this.areaHighlight(area);
      const isSelected = area.node_id === this.selectedAreaId;
      this.ctx.save();
      this.ctx.globalAlpha = highlight || isSelected ? 0.55 : 0.17;
      this.ctx.fillStyle = isSelected ? "#ffe48a" : highlight || fill;
      this.ctx.fillRect(x, y, width, height);
      this.ctx.globalAlpha = 1;
      this.ctx.strokeStyle = isSelected ? "#986f00" : "#3a3a3a";
      this.ctx.lineWidth = isSelected ? 3 : 2;
      this.ctx.strokeRect(x, y, width, height);
      this.ctx.restore();
    }
  }

  drawBuildingAreaOverlays() {
    if (!this.buildingOverlayVisible) return;
    for (const parentArea of this.scene.areas || []) {
      for (const childArea of parentArea.areas || []) {
        if (childArea.metadata?.source === "auto_open_space") continue;
        const globalBounds = childAreaGlobalBounds(parentArea, childArea);
        const [x, y, width, height] = this.transform.rectToScreen(globalBounds);
        const fill = parentArea.rendering?.area_colors?.[childArea.node_id] || "#f1d89b";
        this.ctx.save();
        this.ctx.globalAlpha = 0.48;
        this.ctx.fillStyle = fill;
        this.ctx.fillRect(x, y, width, height);
        this.ctx.globalAlpha = 1;
        this.ctx.strokeStyle = "#6f5f2a";
        this.ctx.setLineDash([4, 3]);
        this.ctx.lineWidth = 1.5;
        this.ctx.strokeRect(x, y, width, height);
        this.ctx.restore();
      }
    }
  }

  buildingOverlayAt(world) {
    if (!this.buildingOverlayVisible) return null;
    for (let parentIndex = (this.scene.areas || []).length - 1; parentIndex >= 0; parentIndex -= 1) {
      const parentArea = this.scene.areas[parentIndex];
      const childAreas = parentArea.areas || [];
      for (let childIndex = childAreas.length - 1; childIndex >= 0; childIndex -= 1) {
        const childArea = childAreas[childIndex];
        if (childArea.metadata?.source === "auto_open_space") continue;
        const globalBounds = childAreaGlobalBounds(parentArea, childArea);
        if (pointInBounds(world, globalBounds)) {
          return { parentArea, childArea, globalBounds };
        }
      }
    }
    return null;
  }

  areaHighlight(area) {
    const space = area.metadata?.space;
    if (this.highlightMode === "indoor" && space === "indoor") {
      return "#b7f7c2";
    }
    return null;
  }

  drawPortals() {
    for (const portal of this.scene.portals || []) {
      if (!portal.segment) continue;
      const [start, end] = portal.segment;
      const [x1, y1] = this.transform.toScreen(start);
      const [x2, y2] = this.transform.toScreen(end);
      this.ctx.save();
      this.ctx.strokeStyle = portal.kind === "door" ? "#8f3f1b" : "#0f6cbd";
      this.ctx.lineWidth = 5;
      this.ctx.lineCap = "round";
      this.ctx.beginPath();
      this.ctx.moveTo(x1, y1);
      this.ctx.lineTo(x2, y2);
      this.ctx.stroke();
      this.ctx.restore();
    }
  }

  drawRoads() {
    for (const road of this.scene.roads?.segments || []) {
      const points = roadPolygon(road).map((point) => this.transform.toScreen(point));
      this.ctx.save();
      this.ctx.fillStyle = "rgb(226 0 0 / 42%)";
      this.ctx.strokeStyle = "rgb(181 0 0 / 68%)";
      this.ctx.lineWidth = 2;
      this.ctx.beginPath();
      points.forEach((point, index) => {
        if (index === 0) this.ctx.moveTo(point[0], point[1]);
        else this.ctx.lineTo(point[0], point[1]);
      });
      this.ctx.closePath();
      this.ctx.fill();
      this.ctx.stroke();
      this.ctx.restore();
    }

    for (const intersection of this.scene.roads?.intersections || []) {
      const [x, y, width, height] = this.transform.rectToScreen(intersection.bounds);
      this.ctx.save();
      this.ctx.fillStyle = "#e00000";
      this.ctx.strokeStyle = "#a80000";
      this.ctx.lineWidth = 2;
      this.ctx.fillRect(x, y, width, height);
      this.ctx.strokeRect(x, y, width, height);
      this.ctx.restore();
    }
  }

  drawWalls() {
    for (const wall of this.scene.walls || []) {
      if (!wall.start || !wall.end) continue;
      const [x1, y1] = this.transform.toScreen(wall.start);
      const [x2, y2] = this.transform.toScreen(wall.end);
      this.ctx.save();
      this.ctx.strokeStyle = wall.wall_type === "exterior" ? "#222222" : "#575757";
      this.ctx.lineWidth = wall.wall_type === "exterior" ? 4 : 2.5;
      this.ctx.lineCap = "square";
      this.ctx.beginPath();
      this.ctx.moveTo(x1, y1);
      this.ctx.lineTo(x2, y2);
      this.ctx.stroke();
      this.ctx.restore();
    }
  }

  drawElements() {
    for (const area of this.scene.areas) {
      if (!this.scene.metadata?.editor_child_scene && isDetailArea(area)) {
        continue;
      }
      for (const element of area.elements) {
        const [x, y, width, height] = this.transform.elementToScreen(element);
        const isHovered = element.node_id === this.hoveredId;
        const isSelected = element.node_id === this.selectedId;
        const isAreaOverlay = element.state_details?.preview_kind === "area";
        const areaOverlayHighlight = isAreaOverlay && this.highlightMode === "indoor" ? "#b7f7c2" : null;
        const elementFill = element.blocks_movement ? "#606060" : "#ffffff";
        this.ctx.save();
        this.ctx.globalAlpha = isAreaOverlay && !isHovered && !isSelected ? 0.55 : 1;
        this.ctx.fillStyle = isHovered || isSelected ? "#ffe48a" : areaOverlayHighlight || elementFill;
        this.ctx.strokeStyle = isHovered || isSelected ? "#986f00" : element.locked ? "#a6a6a6" : "#707070";
        this.ctx.lineWidth = isHovered || isSelected ? 3 : 1.5;
        this.ctx.fillRect(x, y, width, height);
        this.ctx.globalAlpha = 1;
        this.ctx.strokeRect(x, y, width, height);

        if (!element.locked && isSelected) {
          this.ctx.fillStyle = "#0f6cbd";
          this.drawResizeHandles(x, y, width, height);
        }

        this.ctx.restore();
      }
    }
  }

  drawResizeHandles(x, y, width, height) {
    const half = this.handleSize / 2;
    const points = [
      [x, y],
      [x + width, y],
      [x, y + height],
      [x + width, y + height],
    ];
    for (const point of points) {
      this.ctx.fillRect(point[0] - half, point[1] - half, this.handleSize, this.handleSize);
    }
  }

  drawSelectedSpatialHandles() {
    const spatial = this.selectedSpatialHit();
    const bounds = spatialObjectBounds(spatial);
    if (!spatial || isObjectLocked(spatial.object) || !bounds) return;
    const [x, y, width, height] = this.transform.rectToScreen(bounds);
    this.ctx.save();
    this.ctx.strokeStyle = "#986f00";
    this.ctx.lineWidth = 2;
    this.ctx.strokeRect(x, y, width, height);
    this.ctx.fillStyle = "#0f6cbd";
    this.drawResizeHandles(x, y, width, height);
    this.ctx.restore();
  }

  drawAgentStart() {
    return;
  }

  drawAgentOverlay() {
    for (const agent of this.agents) {
      if (!agent.position) continue;
      const [x, y] = this.transform.toScreen(agent.position);
      this.ctx.save();
      this.ctx.fillStyle = agent.color || "#7f4ac9";
      this.ctx.beginPath();
      this.ctx.arc(x, y, 7, 0, Math.PI * 2);
      this.ctx.fill();
      this.ctx.fillStyle = "#1f1f1f";
      this.ctx.font = "12px Segoe UI, sans-serif";
      this.ctx.fillText(agent.name || agent.agent_id, x + 10, y - 2);
      if (agent.behavior) {
        this.ctx.fillStyle = "#616161";
        this.ctx.font = "11px Segoe UI, sans-serif";
        this.ctx.fillText(agent.behavior, x + 10, y + 12);
      }
      this.ctx.restore();
    }
  }

  drawSignalOverlay() {
    if (!this.signalMap?.baseStation) return;
    const [x, y] = this.transform.toScreen(this.signalMap.baseStation.position);
    this.ctx.save();
    this.ctx.strokeStyle = "rgb(15 108 189 / 35%)";
    this.ctx.fillStyle = "#0f6cbd";
    this.ctx.lineWidth = 2;
    this.ctx.beginPath();
    this.ctx.arc(x, y, this.signalMap.radius * this.transform.scale, 0, Math.PI * 2);
    this.ctx.stroke();
    this.ctx.beginPath();
    this.ctx.arc(x, y, 6, 0, Math.PI * 2);
    this.ctx.fill();
    this.ctx.restore();
  }

  drawQosOverlay() {
    if (!this.qosResults) return;
    // Reserved for latency, throughput, packet loss, and congestion overlays.
  }
}

function objectLabel(object) {
  return object.name || object.node_id || object.road_id || object.intersection_id || object.wall_id || "object";
}

function overlayTitle(hit) {
  return [
    `${hit.parentArea.name} / ${hit.childArea.name}`,
    `local: ${formatBounds(hit.childArea.bounds)}`,
    `global: ${formatBounds(hit.globalBounds)}`,
  ].join("\n");
}

function childAreaGlobalBounds(parentArea, childArea) {
  const localBounds = parentArea.rendering?.map_bounds || [
    0,
    0,
    parentArea.bounds[2] - parentArea.bounds[0],
    parentArea.bounds[3] - parentArea.bounds[1],
  ];
  const start = localPointToGlobal([childArea.bounds[0], childArea.bounds[1]], parentArea, localBounds);
  const end = localPointToGlobal([childArea.bounds[2], childArea.bounds[3]], parentArea, localBounds);
  return [start[0], start[1], end[0], end[1]];
}

function localPointToGlobal(point, parentArea, localBounds) {
  const parentWidth = Math.max(1, parentArea.bounds[2] - parentArea.bounds[0]);
  const parentHeight = Math.max(1, parentArea.bounds[3] - parentArea.bounds[1]);
  const localWidth = Math.max(1, localBounds[2] - localBounds[0]);
  const localHeight = Math.max(1, localBounds[3] - localBounds[1]);
  return [
    parentArea.bounds[0] + (point[0] - localBounds[0]) * parentWidth / localWidth,
    parentArea.bounds[1] + (point[1] - localBounds[1]) * parentHeight / localHeight,
  ];
}

function pointInBounds(point, bounds) {
  return point[0] >= bounds[0] && point[0] <= bounds[2] && point[1] >= bounds[1] && point[1] <= bounds[3];
}

function formatBounds(bounds) {
  return `[${bounds.map((value) => Number(value).toFixed(1).replace(/\.0$/, "")).join(", ")}]`;
}

function isObjectLocked(object) {
  return Boolean(object?.locked || object?.metadata?.locked);
}

function isDetailArea(area) {
  return Boolean(area?.metadata?.has_detail_scene || area?.areas?.length || area?.walls?.length || area?.portals?.length);
}

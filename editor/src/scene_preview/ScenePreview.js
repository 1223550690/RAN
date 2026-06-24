import { createTransform, getSceneBounds, hitTestArea, hitTestElement } from "./geometry.js";

export class ScenePreview {
  constructor(canvas, options = {}) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.options = options;
    this.scene = null;
    this.hoveredId = null;
    this.selectedId = null;
    this.selectedAreaId = null;
    this.agents = [];
    this.signalMap = null;
    this.qosResults = null;
    this.highlightMode = "none";
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

  render() {
    const rect = this.canvas.getBoundingClientRect();
    this.ctx.clearRect(0, 0, rect.width, rect.height);
    this.drawBackground(rect.width, rect.height);

    if (!this.scene) {
      return;
    }

    this.transform = createTransform(getSceneBounds(this.scene), rect.width, rect.height, 42, this.view);
    this.drawGrid(rect.width, rect.height);
    this.drawAreas();
    this.drawPortals();
    this.drawElements();
    this.drawAgentStart();
    this.drawAgentOverlay();
    this.drawSignalOverlay();
    this.drawQosOverlay();
  }

  bindEvents() {
    window.addEventListener("resize", () => this.resize());

    this.canvas.addEventListener("mousemove", (event) => {
      if (!this.scene || !this.transform) return;
      const world = this.eventToWorld(event);

      if (this.drag) {
        if (this.drag.mode === "resize") {
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
      const hoveredId = hit?.element.node_id || null;
      if (hit?.element) {
        this.canvas.title = `${hit.element.name} (${hit.element.node_id})`;
      } else {
        const areaHit = hitTestArea(this.scene, world);
        this.canvas.title = areaHit?.area ? `${areaHit.area.name} (${areaHit.area.node_id})` : "";
      }
      if (hoveredId !== this.hoveredId) {
        this.options.onHover?.(hoveredId);
      }
      this.canvas.style.cursor = handle?.cursor || (this.canMoveHit(hit) ? "move" : "default");
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
      const handle = this.resizeHandleAt(local);
      if (handle) {
        this.options.onMoveStart?.({ elementId: handle.element.node_id });
        this.drag = {
          mode: "resize",
          element: handle.element,
          corner: handle.corner,
          anchor: handle.anchor,
        };
        return;
      }
      const hit = hitTestElement(this.scene, world);
      const wasSelected = hit?.element?.node_id === this.selectedId;
      if (hit?.element) {
        this.options.onSelect?.(hit.element.node_id);
      } else {
        const areaHit = hitTestArea(this.scene, world);
        if (areaHit?.area) {
          this.options.onAreaSelect?.(areaHit.area.node_id);
        }
      }
      if (wasSelected && this.canMoveHit(hit)) {
        this.options.onMoveStart?.({ elementId: hit.element.node_id });
        this.drag = { mode: "move", ...hit };
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
      this.view.scaleMultiplier = Math.min(5, Math.max(0.35, this.view.scaleMultiplier * factor));
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
      this.options.onContextMenu?.({
        client: [event.clientX, event.clientY],
        local: this.eventToLocal(event),
        world,
        target: hit,
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
    return hit?.element?.movable && hit.element.node_id === this.selectedId;
  }

  selectedMovableElement() {
    if (!this.selectedId) return null;
    for (const area of this.scene?.areas || []) {
      const element = area.elements.find((item) => item.node_id === this.selectedId);
      if (element?.movable) return element;
    }
    return null;
  }

  resizeHandleAt(localPoint) {
    const element = this.selectedMovableElement();
    if (!element || !this.transform) return null;
    const [x, y, width, height] = this.transform.elementToScreen(element);
    const handles = [
      { corner: "nw", cursor: "nwse-resize", point: [x, y], anchor: [element.center[0] + element.size[0] / 2, element.center[1] + element.size[1] / 2] },
      { corner: "ne", cursor: "nesw-resize", point: [x + width, y], anchor: [element.center[0] - element.size[0] / 2, element.center[1] + element.size[1] / 2] },
      { corner: "sw", cursor: "nesw-resize", point: [x, y + height], anchor: [element.center[0] + element.size[0] / 2, element.center[1] - element.size[1] / 2] },
      { corner: "se", cursor: "nwse-resize", point: [x + width, y + height], anchor: [element.center[0] - element.size[0] / 2, element.center[1] - element.size[1] / 2] },
    ];
    const half = this.handleSize / 2;
    return handles.find((handle) => (
      localPoint[0] >= handle.point[0] - half
      && localPoint[0] <= handle.point[0] + half
      && localPoint[1] >= handle.point[1] - half
      && localPoint[1] <= handle.point[1] + half
    )) ? { ...handles.find((handle) => (
      localPoint[0] >= handle.point[0] - half
      && localPoint[0] <= handle.point[0] + half
      && localPoint[1] >= handle.point[1] - half
      && localPoint[1] <= handle.point[1] + half
    )), element } : null;
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

  drawBackground(width, height) {
    this.ctx.fillStyle = "#f8f8f8";
    this.ctx.fillRect(0, 0, width, height);
  }

  drawGrid(width, height) {
    this.ctx.save();
    this.ctx.strokeStyle = "#ececec";
    this.ctx.lineWidth = 1;
    for (let x = 0; x < width; x += 28) {
      this.ctx.beginPath();
      this.ctx.moveTo(x, 0);
      this.ctx.lineTo(x, height);
      this.ctx.stroke();
    }
    for (let y = 0; y < height; y += 28) {
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

  drawElements() {
    for (const area of this.scene.areas) {
      for (const element of area.elements) {
        const [x, y, width, height] = this.transform.elementToScreen(element);
        const isHovered = element.node_id === this.hoveredId;
        const isSelected = element.node_id === this.selectedId;
        const isAreaOverlay = element.state_details?.preview_kind === "area";
        const areaOverlayHighlight = isAreaOverlay && this.highlightMode === "indoor" ? "#b7f7c2" : null;
        this.ctx.save();
        this.ctx.globalAlpha = isAreaOverlay && !isHovered && !isSelected ? 0.55 : 1;
        this.ctx.fillStyle = isHovered || isSelected ? "#ffe48a" : areaOverlayHighlight || (element.blocks_movement ? "#606060" : "#ffffff");
        this.ctx.strokeStyle = isHovered || isSelected ? "#986f00" : element.movable ? "#707070" : "#404040";
        this.ctx.lineWidth = isHovered || isSelected ? 3 : 1.5;
        this.ctx.fillRect(x, y, width, height);
        this.ctx.globalAlpha = 1;
        this.ctx.strokeRect(x, y, width, height);

        if (element.movable && isSelected) {
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

  drawAgentStart() {
    const point = this.scene.default_agent_start;
    if (!point) return;
    const [x, y] = this.transform.toScreen(point);
    this.ctx.save();
    this.ctx.fillStyle = "#0f6cbd";
    this.ctx.beginPath();
    this.ctx.arc(x, y, 6, 0, Math.PI * 2);
    this.ctx.fill();
    this.ctx.fillStyle = "#1f1f1f";
    this.ctx.font = "12px Segoe UI, sans-serif";
    this.ctx.fillText("start", x + 8, y - 8);
    this.ctx.restore();
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

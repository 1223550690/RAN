import { EditorStore } from "./editorStore.js";
import { renderPropertyEditor, scrollSelectionIntoView, updatePropertyHighlights } from "./propertyEditor.js";
import { ContextMenu } from "./contextMenu.js";
import { sampleScene } from "../scene_model/sampleScene.js";
import { ScenePreview } from "../scene_preview/ScenePreview.js";

const canvas = document.querySelector("#sceneCanvas");
const propertyEditor = document.querySelector("#propertyEditor");
const contextMenuElement = document.querySelector("#contextMenu");
const statusText = document.querySelector("#statusText");
const sceneSelect = document.querySelector("#sceneSelect");
const saveButton = document.querySelector("#saveButton");
const highlightIndoorButton = document.querySelector("#highlightIndoorButton");
const addRoadButton = document.querySelector("#addRoadButton");
const addIntersectionButton = document.querySelector("#addIntersectionButton");
const addPortalButton = document.querySelector("#addPortalButton");
const addWallButton = document.querySelector("#addWallButton");
const coordinateText = document.querySelector("#coordinateText");

const store = new EditorStore(sampleScene);
const contextMenu = new ContextMenu(contextMenuElement, store);
let lastScrolledSelectedId = null;
let lastScrolledSelectedAreaId = null;
let lastScrolledSpatialKey = null;

const preview = new ScenePreview(canvas, {
  onHover: (id) => store.setHover(id),
  onSelect: (id) => store.setSelected(id),
  onAreaSelect: (id) => store.setSelectedArea(id),
  onSpatialSelect: (selection) => store.setSelectedSpatial(selection),
  onMoveStart: () => store.beginMove(),
  onElementMoved: ({ elementId, center }) => store.moveElement(elementId, center),
  onElementResized: ({ elementId, center, size }) => store.resizeElement(elementId, center, size),
  onSpatialMoved: (request) => store.moveSpatialObject(request),
  onSpatialResized: (request) => store.resizeSpatialObject(request),
  onContextMenu: (request) => contextMenu.show(request),
  onCoordinate: (coord) => store.setHoverCoord(coord),
  onSpatialPick: (endpoint) => store.pickPortalEndpoint(endpoint),
});

store.subscribe((state, options) => {
  preview.setScene(state.scene);
  preview.setHovered(state.hoveredId);
  preview.setSelected(state.selectedId);
  preview.setSelectedArea(state.selectedAreaId);
  preview.setSelectedSpatial(state.selectedSpatial);
  preview.setActiveTool(state.activeTool);
  addPortalButton.classList.toggle("active", state.activeTool === "portal");
  coordinateText.textContent = state.hoverCoord ? `x ${state.hoverCoord.x}, y ${state.hoverCoord.y}` : "x -, y -";
  if (options.renderProperties) {
    renderPropertyEditor(propertyEditor, store);
  }
  if (options.updateHighlights) {
    updatePropertyHighlights(propertyEditor, state);
  }
  if (state.selectedId && state.selectedId !== lastScrolledSelectedId) {
    lastScrolledSelectedId = state.selectedId;
    window.setTimeout(() => scrollSelectionIntoView(propertyEditor, state), 0);
  }
  if (state.selectedAreaId && state.selectedAreaId !== lastScrolledSelectedAreaId) {
    lastScrolledSelectedAreaId = state.selectedAreaId;
    window.setTimeout(() => scrollSelectionIntoView(propertyEditor, state), 0);
  }
  const spatialKey = state.selectedSpatial && state.selectedSpatial.type !== "area"
    ? `${state.selectedSpatial.type}:${state.selectedSpatial.id}`
    : null;
  if (spatialKey && spatialKey !== lastScrolledSpatialKey) {
    lastScrolledSpatialKey = spatialKey;
    window.setTimeout(() => scrollSelectionIntoView(propertyEditor, state), 0);
  }
  statusText.textContent = statusLabel(state);
});

document.querySelector("#fitViewButton").addEventListener("click", () => preview.fitView());
saveButton.addEventListener("click", () => saveCurrentScene());
highlightIndoorButton.addEventListener("click", () => setHighlightMode("indoor"));
addRoadButton.addEventListener("click", () => store.addRoadSegment());
addIntersectionButton.addEventListener("click", () => store.addRoadIntersection());
addWallButton.addEventListener("click", () => store.addWall());
addPortalButton.addEventListener("click", () => store.setTool("portal"));

window.addEventListener("keydown", (event) => {
  if (!(event.ctrlKey || event.metaKey)) return;
  const key = event.key.toLowerCase();
  if (key === "z") {
    event.preventDefault();
    store.undo();
  }
  if (key === "s") {
    event.preventDefault();
    saveCurrentScene();
  }
});

document.querySelector("#exportButton").addEventListener("click", () => {
  const blob = new Blob([store.exportJson()], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${store.scene.node_id || "scene"}.json`;
  link.click();
  URL.revokeObjectURL(url);
});

await loadSceneCatalog();
preview.setScene(store.scene);
renderPropertyEditor(propertyEditor, store);
statusText.textContent = statusLabel(store.snapshot());

async function loadSceneCatalog() {
  try {
    const response = await fetch("./data/scenes/index.json", { cache: "no-store" });
    const catalog = await response.json();
    sceneSelect.innerHTML = "";
    for (const scene of catalog.scenes) {
      const option = document.createElement("option");
      option.value = scene.id;
      option.textContent = `${scene.id} / ${scene.name}`;
      option.dataset.path = scene.path;
      sceneSelect.append(option);
    }
    sceneSelect.addEventListener("change", () => loadSelectedScene());
    await loadSelectedScene();
  } catch {
    const option = document.createElement("option");
    option.value = sampleScene.node_id;
    option.textContent = sampleScene.name;
    sceneSelect.append(option);
    store.loadScene(sampleScene.node_id, sampleScene);
  }
}

async function loadSelectedScene() {
  const option = sceneSelect.selectedOptions[0];
  if (!option) return;
  if (option.dataset.temporary === "true" || !option.dataset.path) return;
  store.removeTemporarySceneOptions(sceneSelect);
  const response = await fetch(option.dataset.path, { cache: "no-store" });
  const scene = await response.json();
  store.loadScene(option.value, scene, { scenePath: option.dataset.path });
}

async function saveCurrentScene() {
  try {
    await store.save();
  } catch (error) {
    statusText.textContent = `save failed - ${error.message}`;
  }
}

function statusLabel(state) {
  const selected = state.selectedId ? `selected: ${state.selectedId}` : "ready";
  const saved = state.lastSavedAt ? `last saved ${new Date(state.lastSavedAt).toLocaleTimeString()}` : "not saved";
  const tool = state.activeTool === "portal"
    ? `portal: select ${state.portalDraft.length === 0 ? "first" : "second"} object`
    : selected;
  return `${state.dirty ? "unsaved" : "saved"} - ${saved} - ${tool}`;
}

function setHighlightMode(mode) {
  const current = highlightIndoorButton.classList.contains("active") ? "indoor" : "none";
  const next = current === mode ? "none" : mode;
  preview.setHighlightMode(next);
  highlightIndoorButton.classList.toggle("active", next === "indoor");
}

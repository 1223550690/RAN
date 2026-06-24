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

const store = new EditorStore(sampleScene);
const contextMenu = new ContextMenu(contextMenuElement, store);
let lastScrolledSelectedId = null;
let lastScrolledSelectedAreaId = null;

const preview = new ScenePreview(canvas, {
  onHover: (id) => store.setHover(id),
  onSelect: (id) => store.setSelected(id),
  onAreaSelect: (id) => store.setSelectedArea(id),
  onMoveStart: () => store.beginMove(),
  onElementMoved: ({ elementId, center }) => store.moveElement(elementId, center),
  onElementResized: ({ elementId, center, size }) => store.resizeElement(elementId, center, size),
  onContextMenu: (request) => contextMenu.show(request),
});

store.subscribe((state, options) => {
  preview.setScene(state.scene);
  preview.setHovered(state.hoveredId);
  preview.setSelected(state.selectedId);
  preview.setSelectedArea(state.selectedAreaId);
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
  statusText.textContent = statusLabel(state);
});

document.querySelector("#fitViewButton").addEventListener("click", () => preview.fitView());
saveButton.addEventListener("click", () => store.save());
highlightIndoorButton.addEventListener("click", () => setHighlightMode("indoor"));

window.addEventListener("keydown", (event) => {
  if (!(event.ctrlKey || event.metaKey)) return;
  const key = event.key.toLowerCase();
  if (key === "z") {
    event.preventDefault();
    store.undo();
  }
  if (key === "s") {
    event.preventDefault();
    store.save();
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
    const response = await fetch("./data/scenes/index.json");
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
  const response = await fetch(option.dataset.path);
  const scene = await response.json();
  store.loadScene(option.value, scene);
}

function statusLabel(state) {
  const selected = state.selectedId ? `selected: ${state.selectedId}` : "ready";
  const saved = state.lastSavedAt ? `上次保存 ${new Date(state.lastSavedAt).toLocaleTimeString()}` : "尚未保存";
  return `${state.dirty ? "未保存" : "已保存"} · ${saved} · ${selected}`;
}

function setHighlightMode(mode) {
  const current = highlightIndoorButton.classList.contains("active") ? "indoor" : "none";
  const next = current === mode ? "none" : mode;
  preview.setHighlightMode(next);
  highlightIndoorButton.classList.toggle("active", next === "indoor");
}

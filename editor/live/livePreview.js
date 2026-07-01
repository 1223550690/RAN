import { ScenePreview } from "../src/scene_preview/ScenePreview.js";

const canvas = document.querySelector("#sceneCanvas");
const statusText = document.querySelector("#statusText");
const agentSummary = document.querySelector("#agentSummary");
const ranStatus = document.querySelector("#ranStatus");
const runtimeLog = document.querySelector("#runtimeLog");
const queryLog = document.querySelector("#queryLog");
const coordinateText = document.querySelector("#coordinateText");
const commandForm = document.querySelector("#commandForm");
const commandInput = document.querySelector("#commandInput");

const commandLines = [];

const preview = new ScenePreview(canvas, {
  onCoordinate: (coord) => {
    coordinateText.textContent = `x ${coord.x}, y ${coord.y}`;
  },
});

commandForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const command = commandInput.value.trim();
  if (!command) return;
  commandInput.value = "";
  if (command.toLowerCase() === "clear") {
    commandLines.length = 0;
    renderQueryConsole();
    return;
  }
  commandLines.push(`> ${command}`);
  try {
    const response = await fetch(`/api/map/query?command=${encodeURIComponent(command)}`, { cache: "no-store" });
    const result = await response.json();
    commandLines.push(JSON.stringify(result, null, 2));
  } catch (error) {
    commandLines.push(`error: ${error.message}`);
  }
  trimCommandLines();
  renderQueryConsole();
});

let lastStateLines = [];

async function refresh() {
  try {
    const response = await fetch("../../outputs/live_state.json", { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`state unavailable: ${response.status}`);
    }
    const state = await response.json();
    preview.setScene(state.scene);
    preview.setAgents(state.agents || []);
    renderStatus(state);
    renderConsole(state);
  } catch {
    statusText.textContent = "waiting for outputs/live_state.json";
    ranStatus.textContent = "RAN input waiting";
  } finally {
    window.setTimeout(refresh, 250);
  }
}

function renderStatus(state) {
  statusText.textContent = `tick ${state.tick} - ${state.scene?.name || state.scene?.node_id || "scene"}`;
  agentSummary.innerHTML = "";
}

function renderConsole(state) {
  const requests = state.ran_requests || [];
  ranStatus.textContent = requests.length ? `RAN requests ${requests.length}` : "RAN input disabled";

  lastStateLines = state.console || [];
  renderRuntimeConsole(lastStateLines);
}

function renderRuntimeConsole(stateLines) {
  runtimeLog.innerHTML = "";
  for (const line of stateLines.slice(-60)) {
    const row = document.createElement("div");
    row.className = "console-line";
    row.textContent = line;
    runtimeLog.append(row);
  }
  runtimeLog.scrollTop = runtimeLog.scrollHeight;
}

function renderQueryConsole() {
  queryLog.innerHTML = "";
  const lines = commandLines.slice(-60);
  for (const line of lines) {
    const row = document.createElement("div");
    row.className = "console-line";
    row.textContent = line;
    queryLog.append(row);
  }
  queryLog.scrollTop = queryLog.scrollHeight;
}

function trimCommandLines() {
  if (commandLines.length > 90) {
    commandLines.splice(0, commandLines.length - 90);
  }
}

refresh();

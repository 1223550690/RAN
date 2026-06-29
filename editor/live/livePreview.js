import { ScenePreview } from "../src/scene_preview/ScenePreview.js";

const canvas = document.querySelector("#sceneCanvas");
const statusText = document.querySelector("#statusText");
const agentSummary = document.querySelector("#agentSummary");
const ranStatus = document.querySelector("#ranStatus");
const consoleLog = document.querySelector("#consoleLog");

const preview = new ScenePreview(canvas);

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

  consoleLog.innerHTML = "";
  const lines = state.console || [];
  for (const line of lines.slice(-60)) {
    const row = document.createElement("div");
    row.className = "console-line";
    row.textContent = line;
    consoleLog.append(row);
  }
  consoleLog.scrollTop = consoleLog.scrollHeight;
}

refresh();

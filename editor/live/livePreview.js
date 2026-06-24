import { ScenePreview } from "../src/scene_preview/ScenePreview.js";

const canvas = document.querySelector("#sceneCanvas");
const statusText = document.querySelector("#statusText");
const agentSummary = document.querySelector("#agentSummary");
const llmStatus = document.querySelector("#llmStatus");
const consoleLog = document.querySelector("#consoleLog");

const preview = new ScenePreview(canvas);
let lastTick = null;

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
    llmStatus.textContent = "LLM waiting";
  } finally {
    window.setTimeout(refresh, 250);
  }
}

function renderStatus(state) {
  lastTick = state.tick;
  statusText.textContent = `tick ${state.tick} · ${state.scene?.name || state.scene?.node_id || "scene"}`;
  agentSummary.innerHTML = "";
  for (const agent of state.agents || []) {
    const pill = document.createElement("div");
    pill.className = "agent-pill";
    const dot = document.createElement("span");
    dot.className = "dot";
    dot.style.background = agent.color || "#7f4ac9";
    const text = document.createElement("span");
    const position = agent.position ? `(${agent.position[0].toFixed(2)}, ${agent.position[1].toFixed(2)})` : "";
    const llm = agent.llm_enabled ? ` · LLM ${llmWaitLabel(agent, state.now_seconds)}` : " · local";
    text.textContent = `${agent.name || agent.agent_id}: ${agent.behavior || "idle"} ${position}${llm}`;
    pill.append(dot, text);
    agentSummary.append(pill);
  }
}

function renderConsole(state) {
  const agents = state.agents || [];
  const enabledAgents = agents.filter((agent) => agent.llm_enabled);
  if (!enabledAgents.length) {
    llmStatus.textContent = "LLM disabled";
  } else {
    const wait = Math.min(...enabledAgents.map((agent) => llmWaitSeconds(agent, state.now_seconds)));
    llmStatus.textContent = `LLM next call in ${wait.toFixed(1)}s`;
  }

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

function llmWaitLabel(agent, nowSeconds) {
  if (!agent.next_llm_call_at) {
    return "ready";
  }
  return `${llmWaitSeconds(agent, nowSeconds).toFixed(1)}s`;
}

function llmWaitSeconds(agent, nowSeconds) {
  if (!agent.next_llm_call_at) {
    return 0;
  }
  return Math.max(0, agent.next_llm_call_at - (nowSeconds || 0));
}

refresh();

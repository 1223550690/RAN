import { ScenePreview } from "../src/scene_preview/ScenePreview.js";

const canvas = document.querySelector("#sceneCanvas");
const statusText = document.querySelector("#statusText");
const agentSummary = document.querySelector("#agentSummary");
const ranStatus = document.querySelector("#ranStatus");
const ranSnapshot = document.querySelector("#ranSnapshot");
const runtimeLog = document.querySelector("#runtimeLog");
const coordinateText = document.querySelector("#coordinateText");
const pauseButton = document.querySelector("#pauseButton");
const exportButton = document.querySelector("#exportButton");

const preview = new ScenePreview(canvas, {
  onCoordinate: (coord) => {
    coordinateText.textContent = `x ${coord.x}, y ${coord.y}`;
  },
});
preview.setBuildingWallOverlayVisible(true);

pauseButton.addEventListener("click", () => sendControl("toggle_pause"));
exportButton.addEventListener("click", () => sendControl("export_logs"));

const toggleLogButton = document.querySelector("#toggleLogButton");
toggleLogButton.addEventListener("click", () => {
  const collapsed = runtimeLog.classList.toggle("hidden");
  toggleLogButton.textContent = collapsed ? "Expand Log" : "Collapse Log";
});

let lastStateLines = [];
let lastRanRenderKey = "";
let lastLogRenderKey = "";
let latestPaused = false;

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
    ranSnapshot.replaceChildren(buildSnapshotEmpty("waiting for RAN tick state"));
  } finally {
    window.setTimeout(refresh, latestPaused ? 1000 : 250);
  }
}

function renderStatus(state) {
  statusText.textContent = `tick ${state.tick} - ${state.scene?.name || state.scene?.node_id || "scene"}`;
  latestPaused = Boolean(state.control_state?.paused);
  pauseButton.textContent = latestPaused ? "Resume" : "Pause";
  renderAgentSummary(state.agents || []);
}

function renderAgentSummary(agents) {
  agentSummary.innerHTML = "";
  for (const agent of agents) {
    const badge = document.createElement("div");
    badge.className = "agent-summary-item";
    const color = agent.color || "#7f4ac9";
    const activity = agent.activity_state || agent.lifecycle_status || "unknown";
    const pos = agent.position ? `(${agent.position[0].toFixed(2)}, ${agent.position[1].toFixed(2)})` : "";
    const target = agent.destination_id ? `→ ${agent.destination_id}` : "";
    const progress =
      agent.waypoint_count > 0 ? `wp ${Math.min(agent.waypoint_index + 1, agent.waypoint_count)}/${agent.waypoint_count}` : "";
    const intent = agent.current_intent_id ? `intent ${agent.current_intent_id}` : "";
    const error = agent.error ? `error ${agent.error}` : "";
    const lines = [activity, pos, target, progress, intent, error].filter(Boolean);

    const dot = document.createElement("span");
    dot.className = "agent-summary-dot";
    dot.style.background = color;
    const text = document.createElement("span");
    text.className = "agent-summary-text";
    text.textContent = `${agent.agent_id}: ${lines.join(" ")}`;
    badge.append(dot, text);
    agentSummary.append(badge);
  }
}

function renderConsole(state) {
  const requests = state.ran_requests || [];
  const ranState = state.ran_state || {};
  if (ranState.status) {
    const progress = ranState.progress || {};
    const percent = progress.completion_ratio !== undefined ? `${(progress.completion_ratio * 100).toFixed(1)}%` : "-";
    ranStatus.textContent = `RAN ${ranState.status} ${percent}`;
  } else {
    ranStatus.textContent = requests.length ? `RAN requests ${requests.length}` : "RAN input disabled";
  }

  renderOverview(state, ranState);
  renderAgentCards(state, ranState);
  lastStateLines = state.console || [];
  renderRuntimeConsole(lastStateLines, state.control_state);
}

/* ------------------------------------------------------------------ */
/* 底部概要面板:仅显示 tick / agent 数 / 各 agent 状态 / RAN 总进度       */
/* ------------------------------------------------------------------ */

function renderOverview(state, ranState) {
  const agents = state.agents || [];
  const overviewStatus = document.querySelector("#overviewStatus");
  const paused = Boolean(state.control_state?.paused);
  overviewStatus.textContent = paused ? "paused" : "running";
  overviewStatus.classList.toggle("paused", paused);

  const body = document.querySelector("#overviewBody");
  body.innerHTML = "";

  // 仿真元信息行
  const meta = document.createElement("div");
  meta.className = "overview-meta";
  const sceneName = state.scene?.name || state.scene?.node_id || state.scene?.scene_id || "scene";
  const uptime = state.uptime_seconds !== undefined ? `${state.uptime_seconds.toFixed(1)}s` : "-";
  const items = [
    `tick ${state.tick ?? "-"}`,
    `agents ${agents.length}`,
    `scene ${sceneName}`,
    `uptime ${uptime}`,
  ];
  for (const item of items) {
    const chip = document.createElement("span");
    chip.className = "overview-chip";
    chip.textContent = item;
    meta.append(chip);
  }
  body.append(meta);

  // 每 agent 一行概要
  if (agents.length) {
    const list = document.createElement("div");
    list.className = "overview-agents";
    for (const agent of agents) {
      list.append(buildOverviewAgentRow(agent));
    }
    body.append(list);
  } else {
    const empty = document.createElement("div");
    empty.className = "overview-empty";
    empty.textContent = "no agents";
    body.append(empty);
  }

  // RAN 汇总行
  body.append(buildOverviewRanRow(ranState));
}

function buildOverviewAgentRow(agent) {
  const row = document.createElement("div");
  row.className = "overview-agent-row";
  const color = agent.color || "#7f4ac9";
  const activity = agent.activity_state || agent.lifecycle_status || "unknown";
  const pos = agent.position ? `(${agent.position[0].toFixed(1)}, ${agent.position[1].toFixed(1)})` : "";
  const target = agent.destination_id ? `→ ${agent.destination_id}` : "";
  const progress =
    agent.waypoint_count > 0 ? `wp ${Math.min(agent.waypoint_index + 1, agent.waypoint_count)}/${agent.waypoint_count}` : "";
  const intent = agent.current_intent_id ? `intent ${agent.current_intent_id}` : "";
  const error = agent.error ? `error ${agent.error}` : "";

  const dot = document.createElement("span");
  dot.className = "agent-summary-dot";
  dot.style.background = color;
  const id = document.createElement("span");
  id.className = "overview-agent-id";
  id.textContent = agent.agent_id;
  const badge = document.createElement("span");
  badge.className = `status-badge status-${activity.toLowerCase()}`;
  badge.textContent = activity;
  const detail = document.createElement("span");
  detail.className = "overview-agent-detail";
  detail.textContent = [pos, target, progress, intent, error].filter(Boolean).join("  ");

  row.append(dot, id, badge, detail);
  return row;
}

function buildOverviewRanRow(ranState) {
  const row = document.createElement("div");
  row.className = "overview-ran-row";
  const status = ranState.status || "no RAN state";
  const progress = ranState.progress || {};
  const delivered = progress.delivered_bytes ?? "-";
  const requested = progress.requested_bytes ?? "-";
  const ratio = progress.completion_ratio !== undefined ? `(${fmtPct(progress.completion_ratio)})` : "";
  const services = Array.isArray(ranState.service_states) ? ranState.service_states.length : "-";
  row.textContent = `RAN ${status}  services ${services}  delivered ${fmtBytes(delivered)} / ${fmtBytes(requested)} ${ratio}`;
  return row;
}

/* ------------------------------------------------------------------ */
/* 右侧:按 agent 分卡片(状态 + 网络详情)                                 */
/* ------------------------------------------------------------------ */

function renderAgentCards(state, ranState) {
  const ranByAgent = {};
  if (Array.isArray(ranState.service_states)) {
    for (const service of ranState.service_states) {
      ranByAgent[service.agent_id] = service;
    }
  }
  const agents = state.agents || [];
  ranSnapshot.innerHTML = "";
  if (!agents.length) {
    ranSnapshot.append(buildSnapshotEmpty("no agents"));
    return;
  }
  const grid = document.createElement("div");
  grid.className = "agent-cards";
  for (const agent of agents) {
    grid.append(buildAgentCard(agent, ranByAgent[agent.agent_id]));
  }
  ranSnapshot.append(grid);
}

function buildAgentCard(agent, service) {
  const card = document.createElement("div");
  card.className = "agent-card";
  const color = agent.color || "#7f4ac9";
  const activity = agent.activity_state || agent.lifecycle_status || "unknown";

  // 头部
  const head = document.createElement("div");
  head.className = "agent-card-head";
  const dot = document.createElement("span");
  dot.className = "agent-summary-dot";
  dot.style.background = color;
  const id = document.createElement("span");
  id.className = "agent-card-id";
  id.textContent = agent.agent_id;
  const badge = document.createElement("span");
  badge.className = `status-badge status-${activity.toLowerCase()}`;
  badge.textContent = activity;
  head.append(dot, id, badge);
  card.append(head);

  // 状态区
  const status = document.createElement("div");
  status.className = "agent-card-section";
  const pos = agent.position ? `(${agent.position[0].toFixed(1)}, ${agent.position[1].toFixed(1)})` : "-";
  const target = agent.destination_id || "-";
  const progress =
    agent.waypoint_count > 0
      ? `${Math.min(agent.waypoint_index + 1, agent.waypoint_count)}/${agent.waypoint_count}`
      : "-";
  const intent = agent.current_intent_id || "-";
  appendKeyValue(status, "位置", pos);
  appendKeyValue(status, "目标", target);
  appendKeyValue(status, "路径", progress);
  appendKeyValue(status, "意图", intent);
  if (agent.error) {
    appendKeyValue(status, "错误", agent.error);
  }
  card.append(status);

  // 网络区(RAN 服务详情)
  const net = document.createElement("div");
  net.className = "agent-card-section agent-card-net";
  if (!service) {
    const waiting = document.createElement("div");
    waiting.className = "agent-card-waiting";
    waiting.textContent = "等待意图提交 / 无 RAN 服务";
    net.append(waiting);
  } else {
    const result = service.result || {};
    const qos = result.qos || {};
    const progressInfo = service.progress || {};
    const channel = service.channel || {};
    const allocation = service.allocation || {};
    const transmission = service.transmission || {};
    const qosFlow = service.qos_flow || {};
    const drb = service.drb || {};
    appendKeyValue(net, "服务", service.service_instance_id || "-");
    appendKeyValue(net, "slice", service.slice_id || result.slice_id || "-");
    appendKeyValue(net, "qfi/drb", `${qosFlow.qfi ?? "-"} / ${drb.drb_id ?? "-"}`);
    appendKeyValue(net, "信道", `cqi ${channel.cqi ?? "-"}  sinr ${fmt(channel.sinr_db)}dB`);
    appendKeyValue(net, "分配", `prbs ${allocation.prbs ?? "-"}  mcs ${allocation.mcs ?? "-"}  layers ${allocation.layers ?? "-"}`);
    appendKeyValue(net, "传输", `tx ${fmtBytes(transmission.successful_bytes ?? 0)}  fail ${fmtBytes(transmission.failed_bytes ?? 0)}`);
    const delivered = progressInfo.delivered_bytes ?? 0;
    const requested = progressInfo.requested_bytes ?? "-";
    appendKeyValue(net, "交付", `${fmtBytes(delivered)} / ${fmtBytes(requested)}`);
    const ratio = progressInfo.completion_ratio !== undefined ? progressInfo.completion_ratio : 0;
    net.append(buildProgressBar(ratio));
  }
  card.append(net);

  return card;
}

function appendKeyValue(container, key, value) {
  const row = document.createElement("div");
  row.className = "agent-card-kv";
  const k = document.createElement("span");
  k.className = "agent-card-k";
  k.textContent = key;
  const v = document.createElement("span");
  v.className = "agent-card-v";
  v.textContent = value;
  row.append(k, v);
  container.append(row);
}

function buildProgressBar(ratio) {
  const wrap = document.createElement("div");
  wrap.className = "progress-bar";
  const fill = document.createElement("div");
  fill.className = "progress-fill";
  const clamped = Math.max(0, Math.min(1, ratio));
  fill.style.width = `${(clamped * 100).toFixed(1)}%`;
  const label = document.createElement("span");
  label.className = "progress-label";
  label.textContent = fmtPct(clamped);
  wrap.append(fill, label);
  return wrap;
}

function fmtBytes(value) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "-";
  if (value >= 1024 * 1024 * 1024) return `${(value / (1024 * 1024 * 1024)).toFixed(2)}GB`;
  if (value >= 1024 * 1024) return `${(value / (1024 * 1024)).toFixed(1)}MB`;
  if (value >= 1024) return `${(value / 1024).toFixed(1)}KB`;
  return `${value}B`;
}

function buildSnapshotEmpty(text) {
  const row = document.createElement("div");
  row.className = "ran-snapshot-empty";
  row.textContent = text;
  return row;
}

function fmt(value) {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(3) : "-";
}

function fmtPct(value) {
  return typeof value === "number" && Number.isFinite(value) ? `${(value * 100).toFixed(2)}%` : "-";
}

function renderRuntimeConsole(stateLines, controlState = {}) {
  const lastLine = stateLines[stateLines.length - 1] || "";
  const renderKey = `${controlState?.paused ? "paused" : "running"}:${controlState?.log_count ?? stateLines.length}:${lastLine}`;
  if (controlState?.paused && renderKey === lastLogRenderKey) {
    return;
  }
  lastLogRenderKey = renderKey;
  runtimeLog.innerHTML = "";
  for (const line of stateLines.slice(-60)) {
    const row = document.createElement("div");
    row.className = "console-line";
    row.textContent = line;
    runtimeLog.append(row);
  }
  runtimeLog.scrollTop = runtimeLog.scrollHeight;
}

async function sendControl(action) {
  try {
    const response = await fetch(`/api/simulation/control?action=${encodeURIComponent(action)}`, {
      method: "POST",
      cache: "no-store",
    });
    const result = await response.json();
    if (action === "export_logs" && result.export?.path) {
      appendRuntimeLine(`exported logs: ${result.export.path}`);
    }
  } catch (error) {
    appendRuntimeLine(`control error: ${error.message}`);
  }
}

function appendRuntimeLine(text) {
  const row = document.createElement("div");
  row.className = "console-line";
  row.textContent = text;
  runtimeLog.append(row);
  runtimeLog.scrollTop = runtimeLog.scrollHeight;
}

refresh();

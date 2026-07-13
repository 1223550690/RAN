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
  agentSummary.innerHTML = "";
}

function renderConsole(state) {
  const requests = state.ran_requests || [];
  const ranState = state.ran_state || {};
  const ranLines = formatRanStateLines(ranState);
  if (ranState.status) {
    const progress = ranState.progress || {};
    const percent = progress.completion_ratio !== undefined ? `${(progress.completion_ratio * 100).toFixed(1)}%` : "-";
    ranStatus.textContent = `RAN ${ranState.status} ${percent}`;
  } else {
    ranStatus.textContent = requests.length ? `RAN requests ${requests.length}` : "RAN input disabled";
  }

  renderRanSnapshot(ranLines, state.control_state);
  lastStateLines = state.console || [];
  renderRuntimeConsole(lastStateLines, state.control_state);
}

function renderRanSnapshot(lines, controlState = {}) {
  const renderKey = `${controlState?.paused ? "paused" : "running"}:${lines.join("\n")}`;
  if (controlState?.paused && renderKey === lastRanRenderKey) {
    return;
  }
  lastRanRenderKey = renderKey;
  ranSnapshot.innerHTML = "";
  if (!lines.length) {
    ranSnapshot.append(buildSnapshotEmpty("RAN tick state not available"));
    return;
  }
  for (const line of lines) {
    const row = document.createElement("div");
    row.className = "ran-snapshot-line";
    for (const part of splitSnapshotLine(line)) {
      const item = document.createElement("div");
      item.className = "ran-snapshot-item";
      item.textContent = part;
      row.append(item);
    }
    ranSnapshot.append(row);
  }
}

function splitSnapshotLine(line) {
  const parts = [];
  const tokens = line.split(/\s+/).filter(Boolean);
  let index = 0;
  if (tokens[0] === "ran" && tokens[1] && !tokens[1].includes("=")) {
    parts.push(`status=${tokens[1]}`);
    index = 2;
  } else if (tokens[0] === "ran") {
    index = 1;
  }
  while (index < tokens.length) {
    const token = tokens[index];
    if (token.startsWith("pos=(") && index + 1 < tokens.length && !token.endsWith(")")) {
      parts.push(`${token} ${tokens[index + 1]}`);
      index += 2;
      continue;
    }
    if (token === "/" && parts.length && index + 1 < tokens.length) {
      parts[parts.length - 1] = `${parts[parts.length - 1]} / ${tokens[index + 1]}`;
      index += 2;
      continue;
    }
    parts.push(token);
    index += 1;
  }
  return parts;
}

function buildSnapshotEmpty(text) {
  const row = document.createElement("div");
  row.className = "ran-snapshot-empty";
  row.textContent = text;
  return row;
}

function formatRanStateLines(ranState) {
  if (!ranState || !ranState.status) return [];
  const result = ranState.result || {};
  const qos = result.qos || {};
  const progress = ranState.progress || {};
  const channel = ranState.channel || {};
  const allocation = ranState.scheduler_result?.allocations?.[0] || {};
  const transmission = ranState.transmission || {};
  const gnb = ranState.gnb || {};
  const ue = ranState.ue_request || {};
  const drb = ranState.drb || {};
  const qosFlow = ranState.qos_flow || {};
  return [
    `ran ${ranState.status} tick=${ranState.tick} ue=${ue.ue_id || "-"} gnb=${gnb.gnb_id || "-"} pos=(${gnb.position?.x ?? "-"}, ${gnb.position?.y ?? "-"}) slice=${result.slice_id || "-"} qfi=${qosFlow.qfi ?? "-"} drb=${drb.drb_id || "-"} cqi=${channel.cqi ?? "-"} sinr=${fmt(channel.sinr_db)}dB prbs=${allocation.prbs ?? "-"} mcs=${allocation.mcs ?? "-"}`,
    `ran tx=${transmission.successful_bytes ?? "-"} fail=${transmission.failed_bytes ?? "-"} total=${progress.delivered_bytes ?? result.delivered_bytes ?? "-"} / ${progress.requested_bytes ?? result.requested_bytes ?? "-"} remaining_payload=${progress.remaining_payload_bytes ?? "-"} queue_bytes=${progress.remaining_queue_bytes ?? "-"} completion_ratio=${fmtPct(progress.completion_ratio)} remaining_ratio=${fmtPct(progress.remaining_ratio)} tick_throughput_mbps=${fmt(qos.throughput_mbps)} loss_rate=${fmtPct(qos.packet_loss_rate)} dropped=${progress.dropped_bytes ?? "-"}`,
  ];
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

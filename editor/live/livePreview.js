/* ================= 国际化 ================= */
const I18N = {
  zh: {
    'overview.title': 'Simulation Overview',
    'overview.tick': 'tick', 'overview.agents': 'agents', 'overview.time': '用时',
    'overview.services': '活跃服务', 'overview.delivered': '交付', 'overview.running': '运行中',
    'overview.pause': '暂停', 'overview.resume': '继续', 'overview.export': '导出 Logs',
    'overview.waiting': '等待数据…', 'overview.updated': '更新',
    'map.hint': '悬停查看对象信息 · 浅色缺口 = 可通行',
    'map.passable': '可通行', 'map.road': '大道', 'map.junction': '交汇', 'map.boundary': '边界',
    'chart.throughput': '系统吞吐量(UL/DL)', 'chart.prb': 'PRB 利用率', 'chart.mcs': 'MCS 分布',
    'chart.snr': '平均 SINR / QoS 时延',
    'agent.waiting': '等待意图提交 / 无 RAN 服务',
    'agent.pos': '位置', 'agent.dest': '目标', 'agent.intent': '意图', 'agent.cp': '控制面',
    'agent.path': '路径', 'agent.role': '角色', 'agent.error': '错误',
    'agent.roleMap': { student: '学生', teacher: '教师', staff: '职员' },
    'agent.intentMap': { message: '发送消息', video_upload: '上传视频', video_download: '下载视频', video_call: '视频通话', file_transfer: '传输文件' },
    'chart.ul': 'UL KB/tick', 'chart.dl': 'DL KB/tick', 'chart.prbLabel': 'PRB 利用率 %',
    'chart.mcsLabel': 'MCS 档位', 'chart.snrLabel': 'SINR dB', 'chart.delayLabel': '时延 ms',
  },
  en: {
    'overview.title': 'Simulation Overview',
    'overview.tick': 'tick', 'overview.agents': 'agents', 'overview.time': 'elapsed',
    'overview.services': 'active services', 'overview.delivered': 'delivered', 'overview.running': 'running',
    'overview.pause': 'Pause', 'overview.resume': 'Resume', 'overview.export': 'Export Logs',
    'overview.waiting': 'Waiting for data…', 'overview.updated': 'Updated',
    'map.hint': 'Hover for details · light gap = passable',
    'map.passable': 'passable', 'map.road': 'road', 'map.junction': 'junction', 'map.boundary': 'boundary',
    'chart.throughput': 'Throughput (UL/DL)', 'chart.prb': 'PRB Utilization', 'chart.mcs': 'MCS Distribution',
    'chart.snr': 'Avg SINR / QoS Delay',
    'agent.waiting': 'Waiting for intent / no RAN service',
    'agent.pos': 'Position', 'agent.dest': 'Target', 'agent.intent': 'Intent', 'agent.cp': 'Control plane',
    'agent.path': 'Path', 'agent.role': 'Role', 'agent.error': 'Error',
    'agent.roleMap': { student: 'Student', teacher: 'Teacher', staff: 'Staff' },
    'agent.intentMap': { message: 'Send message', video_upload: 'Upload video', video_download: 'Download video', video_call: 'Video call', file_transfer: 'Transfer file' },
    'chart.ul': 'UL KB/tick', 'chart.dl': 'DL KB/tick', 'chart.prbLabel': 'PRB util %',
    'chart.mcsLabel': 'MCS level', 'chart.snrLabel': 'SINR dB', 'chart.delayLabel': 'Delay ms',
  },
};
let lang = localStorage.getItem('preview-lang') || 'zh';
function t(key) {
  const v = I18N[lang][key];
  return typeof v === 'string' ? v : key;
}
function applyI18n() {
  document.querySelectorAll('[data-i18n]').forEach((el) => { el.textContent = t(el.dataset.i18n); });
  document.getElementById('btn-lang').textContent = lang === 'zh' ? 'EN' : '中文';
}
function toggleLang() {
  lang = lang === 'zh' ? 'en' : 'zh';
  localStorage.setItem('preview-lang', lang);
  applyI18n();
  renderAgents(); // 卡片内嵌文案需重渲染
}
document.getElementById('btn-lang').addEventListener('click', toggleLang);

/* ================= 状态 ================= */
let paused = false;
let lastUpdateAt = 0;
let tick = 0;
let emptyFetches = 0;
const MAX_POINTS = 60;
const series = { ul: [], dl: [], prb: [], mcs: [], sinr: [], delay: [], delivered: [] };
let lastRan = null;
let serviceHistory = [];

/* ================= 地图渲染(编辑器场景 JSON) ================= */
const DOOR_KINDS = new Set(['door', 'building_entrance', 'open_passage', 'entrance']);

function collinearOverlap(a, b, c, d, eps = 0.1) {
  const cross = (b[0] - a[0]) * (d[1] - c[1]) - (b[1] - a[1]) * (d[0] - c[0]);
  if (Math.abs(cross) > eps * Math.max(1, Math.abs(b[0] - a[0]) + Math.abs(b[1] - a[1]))) return false;
  if (Math.abs(b[0] - a[0]) >= Math.abs(b[1] - a[1])) {
    const lo1 = Math.min(a[0], b[0]), hi1 = Math.max(a[0], b[0]);
    const lo2 = Math.min(c[0], d[0]), hi2 = Math.max(c[0], d[0]);
    return Math.max(lo1, lo2) <= Math.min(hi1, hi2) + eps && Math.abs(a[1] - c[1]) <= eps * 2;
  }
  const lo1 = Math.min(a[1], b[1]), hi1 = Math.max(a[1], b[1]);
  const lo2 = Math.min(c[1], d[1]), hi2 = Math.max(c[1], d[1]);
  return Math.max(lo1, lo2) <= Math.min(hi1, hi2) + eps && Math.abs(a[0] - c[0]) <= eps * 2;
}

function edgeEndpoints(e) {
  if ('x1' in e) return [[e.x1, e.y], [e.x2, e.y]];
  return [[e.x, e.y1], [e.x, e.y2]];
}

function roadPath(seg) {
  let [t1, t2] = edgeEndpoints(seg.top);
  let [b1, b2] = edgeEndpoints(seg.bottom);
  const horizontal = Math.abs(t2[0] - t1[0]) >= Math.abs(t2[1] - t1[1]);
  const key = (p) => (horizontal ? p[0] : p[1]);
  [t1, t2] = [t1, t2].sort((p, q) => key(p) - key(q));
  [b1, b2] = [b1, b2].sort((p, q) => key(p) - key(q));
  const side = (a, b, sign) => {
    const dx = b[0] - a[0], dy = b[1] - a[1];
    const len = Math.max(1e-6, Math.hypot(dx, dy));
    const nx = -dy / len, ny = dx / len;
    const c1 = [a[0] + dx * 0.33 + nx * sign * 12, a[1] + dy * 0.33 + ny * sign * 12];
    const c2 = [a[0] + dx * 0.66 + nx * sign * 12, a[1] + dy * 0.66 + ny * sign * 12];
    return `C${c1[0].toFixed(1)},${c1[1].toFixed(1)} ${c2[0].toFixed(1)},${c2[1].toFixed(1)} ${b[0]},${b[1]}`;
  };
  return `M${t1[0]},${t1[1]} ${side(t1, b1, 1)} L${b2[0]},${b2[1]} ${side(b2, t2, 1)} L${t2[0]},${t2[1]} Z`;
}

function renderMap(scene) {
  const svg = document.getElementById('map');
  const parts = [];

  // 顶层区域
  for (const area of scene.areas) {
    const [x0, y0, x1, y1] = area.bounds;
    const cls = area.metadata && area.metadata.space === 'indoor' ? 'area indoor' : 'area outdoor';
    parts.push(`<rect x="${x0}" y="${y0}" width="${x1 - x0}" height="${y1 - y0}" class="${cls}" data-tip="${area.name}"></rect>`);
  }

  // 道路(曲线侧边)
  for (const seg of scene.roads.segments || []) {
    parts.push(`<path d="${roadPath(seg)}" class="road" data-tip="${seg.name} · ${t('map.road')}"></path>`);
  }
  // junction:从顶层 portals(road_junction)segment 包围盒
  const juncBoxes = {};
  for (const p of scene.portals || []) {
    if (p.kind !== 'road_junction' || !p.segment) continue;
    for (const an of p.areas || []) {
      if (String(an).includes('junction')) {
        (juncBoxes[an] = juncBoxes[an] || []).push(p.segment);
      }
    }
  }
  for (const [name, segs] of Object.entries(juncBoxes)) {
    const xs = segs.flatMap((s) => [s[0][0], s[1][0]]);
    const ys = segs.flatMap((s) => [s[0][1], s[1][1]]);
    const x0 = Math.min(...xs), y0 = Math.min(...ys);
    parts.push(`<rect x="${x0}" y="${y0}" width="${Math.max(...xs) - x0}" height="${Math.max(...ys) - y0}" class="road-junction" data-tip="${name} · ${t('map.junction')}"></rect>`);
  }

  // 房间(递归)+ 房间边界
  const rooms = [];
  const roomEdges = [];
  const collectRooms = (parent, ox, oy, depth) => {
    for (const child of parent.areas || []) {
      const cx = ox + child.bounds[0], cy = oy + child.bounds[1];
      // ox/oy = 父区域全局原点(渲染时再加 child.bounds 一次,不能双重偏移)
      rooms.push({ room: child, ox, oy });
      const [x0, y0, x1, y1] = child.bounds;
      // 全局坐标 = 父原点 + 局部 bounds(一次偏移;cx/cy 已含 child.bounds,不可再用)
      const gx0 = ox + x0, gy0 = oy + y0, gx1 = ox + x1, gy1 = oy + y1;
      const edges = [
        [[gx0, gy0], [gx1, gy0]], [[gx1, gy0], [gx1, gy1]],
        [[gx1, gy1], [gx0, gy1]], [[gx0, gy1], [gx0, gy0]],
      ];
      for (const e of edges) roomEdges.push({ e, name: child.name });
      collectRooms(child, cx, cy, depth + 1);
    }
  };
  for (const top of scene.areas) collectRooms(top, top.bounds[0], top.bounds[1], 0);
  for (const { room, ox, oy } of rooms) {
    const [x0, y0, x1, y1] = room.bounds;
    parts.push(`<rect x="${x0 + ox}" y="${y0 + oy}" width="${x1 - x0}" height="${y1 - y0}" class="room" data-tip="${room.name}"></rect>`);
  }

  // 共享边 → 门;非共享边 → 内墙
  const shared = new Set();
  for (let i = 0; i < roomEdges.length; i++) {
    for (let j = i + 1; j < roomEdges.length; j++) {
      const [a, b] = roomEdges[i].e, [c, d] = roomEdges[j].e;
      if (collinearOverlap(a, b, c, d)) { shared.add(i); shared.add(j); }
    }
  }
  const topWalls = [];
  for (const area of scene.areas) {
    const [ox, oy] = area.bounds;
    for (const w of area.walls || []) {
      if (w.blocks_movement !== false) topWalls.push({ w, ox, oy });
    }
  }
  roomEdges.forEach(({ e, name }, idx) => {
    if (shared.has(idx)) return;
    const [a, b] = e;
    const onWall = topWalls.some(({ w, ox, oy }) => collinearOverlap(
      [w.segment[0][0] + ox, w.segment[0][1] + oy], [w.segment[1][0] + ox, w.segment[1][1] + oy], a, b));
    if (!onWall) {
      parts.push(`<line x1="${a[0]}" y1="${a[1]}" x2="${b[0]}" y2="${b[1]}" class="wall-inner" data-tip="${name} · ${t('map.boundary')}"></line>`);
    }
  });

  // 顶层墙
  for (const { w, ox, oy } of topWalls) {
    const cls = w.wall_type === 'exterior' ? 'wall-exterior' : 'wall-interior';
    parts.push(`<line x1="${w.segment[0][0] + ox}" y1="${w.segment[0][1] + oy}" x2="${w.segment[1][0] + ox}" y2="${w.segment[1][1] + oy}" class="${cls}" data-tip="${w.name} · ${w.wall_type}"></line>`);
  }

  // 门:区域级 portals(递归,局部坐标偏移)+ 顶层道路级 portals
  const pushDoor = (name, seg) => {
    if (!seg) return;
    parts.push(`<line x1="${seg[0][0]}" y1="${seg[0][1]}" x2="${seg[1][0]}" y2="${seg[1][1]}" class="door" data-tip="${name} · ${t('map.passable')}"></line>`);
  };
  const collectDoors = (area, ox, oy) => {
    for (const p of area.portals || []) {
      if (!DOOR_KINDS.has(p.kind) || p.open === false || !p.segment) continue;
      const s = [[p.segment[0][0] + ox, p.segment[0][1] + oy], [p.segment[1][0] + ox, p.segment[1][1] + oy]];
      pushDoor(p.name, s);
    }
    for (const child of area.areas || []) collectDoors(child, ox + child.bounds[0], oy + child.bounds[1]);
  };
  for (const top of scene.areas) collectDoors(top, top.bounds[0], top.bounds[1]);
  for (const p of scene.portals || []) {
    if (!DOOR_KINDS.has(p.kind) || p.open === false) continue;
    pushDoor(p.name, p.segment);
  }

  svg.innerHTML = parts.join('\n');

  // tooltip
  const panel = document.querySelector('.map-panel');
  const tip = document.getElementById('tooltip');
  document.querySelectorAll('#map [data-tip]').forEach((el) => {
    el.addEventListener('mousemove', (e) => {
      const rect = svg.getBoundingClientRect();
      const px = e.clientX - panel.getBoundingClientRect().left + 14;
      const py = e.clientY - panel.getBoundingClientRect().top + 14;
      tip.style.display = 'block';
      tip.textContent = el.dataset.tip;
      tip.style.left = px + 'px';
      tip.style.top = py + 'px';
    });
    el.addEventListener('mouseleave', () => { tip.style.display = 'none'; });
  });
}

fetch('/editor/data/scenes/bristol_topology.json')
  .then((r) => r.json())
  .then(renderMap)
  .catch((err) => console.warn('场景加载失败:', err));

/* ================= Banner / Agent 卡片 ================= */
const AGENT_COLORS = ['#4A87BE', '#7D5260', '#4C9E74', '#B08A3E', '#5E7894'];
/* agent 状态 → 红黄绿(阶段色) */
const STATE_COLORS = {
  FAILED: '#B3261E', ERROR: '#B3261E',           // 红:失败/错误
  READY: '#B08A3E', PLANNING: '#B08A3E', NETWORK_PENDING: '#B08A3E', WAITING: '#B08A3E',  // 黄:准备/规划/等待
  ACTIVE: '#2E8B57', RUNNING: '#2E8B57', WALKING: '#4C9E74', NETWORK_ACTIVE: '#2E8B57',  // 绿:进行中
  COMPLETED: '#1E6B42', DONE: '#1E6B42',         // 深绿:完成
};
function stateColor(status) {
  return STATE_COLORS[String(status || '').toUpperCase()] || '#8A93A3';
}
function fmtBytes(n) {
  if (n === null || n === undefined) return '-';
  if (n >= 1073741824) return (n / 1073741824).toFixed(1) + 'GB';
  if (n >= 1048576) return (n / 1048576).toFixed(0) + 'MB';
  if (n >= 1024) return (n / 1024).toFixed(0) + 'KB';
  return n + 'B';
}
function intentLabel(intent, svc) {
  const map = I18N[lang]['agent.intentMap'] || {};
  const type = (svc && svc.intent_type) || intent || '';
  const kind = String(type).replace(/_\d+$/, '');
  const label = map[kind] || (svc && svc.intent_type) || intent || '-';
  const bytes = svc && svc.progress ? svc.progress.requested_bytes : null;
  return bytes != null ? `${label} ${fmtBytes(bytes)}` : label;
}

function updateBanner(ran, nowSeconds) {
  document.getElementById('st-tick').textContent = tick;
  document.getElementById('st-agents').textContent = ran.agent_count ?? 0;
  const elapsed = nowSeconds !== undefined && nowSeconds !== null ? nowSeconds : tick * 0.5;
  document.getElementById('st-time').textContent = elapsed.toFixed(1) + 's';
  const active = (ran.service_states || []).filter((s) => s.status && s.status !== 'COMPLETED' && s.status !== 'FAILED');
  document.getElementById('st-services').textContent = active.length;
  const prog = ran.progress || {};
  const ratio = prog.completion_ratio !== undefined ? prog.completion_ratio : 0;
  document.getElementById('st-delivered').textContent = Math.round(ratio * 100) + '%';
  // 概要:每 agent 状态行 + RAN 总进度条
  const summary = document.getElementById('banner-summary');
  if (!summary) return;
  const states = ran.agent_states || [];
  const parts = states.map((a) => {
    const wp = a.waypoint_count > 0 ? `${Math.min(a.waypoint_index + 1, a.waypoint_count)}/${a.waypoint_count}` : '';
    return `<span class="banner-agent"><i class="dot" style="background:${AGENT_COLORS[states.indexOf(a) % AGENT_COLORS.length]}"></i>${a.agent_id} · ${a.status}${wp ? ' · wp ' + wp : ''}</span>`;
  }).join('');
  summary.innerHTML = `<span class="banner-ratio"><b>${Math.round(ratio * 100)}%</b></span><div class="banner-track"><div class="banner-fill" style="width:${(ratio * 100).toFixed(1)}%"></div></div>${parts}`;
}

/* 地图上的 agent 路线图层(每次 poll 更新) */
/* 地图 tooltip:事件委托,动态元素无需重复绑定 */
function bindTooltip() {
  const panel = document.querySelector('.map-panel');
  const tip = document.getElementById('tooltip');
  panel.addEventListener('mousemove', (e) => {
    const el = e.target.closest ? e.target.closest('[data-tip]') : null;
    if (!el) { tip.style.display = 'none'; return; }
    const px = e.clientX - panel.getBoundingClientRect().left + 14;
    const py = e.clientY - panel.getBoundingClientRect().top + 14;
    tip.style.display = 'block';
    tip.textContent = el.dataset.tip;
    tip.style.left = px + 'px';
    tip.style.top = py + 'px';
  });
  panel.addEventListener('mouseleave', () => { tip.style.display = 'none'; });
}
function renderRoutes(ran) {
  const map = document.getElementById('map');
  if (!map) return;
  // 清除旧路线图层(合并进主 SVG,避免独立定位 SVG 的兼容问题)
  map.querySelectorAll('.route, .agent-dot').forEach((el) => el.remove());
  const states = ran.agent_states || [];
  const frag = document.createDocumentFragment();
  states.forEach((a, i) => {
    const color = AGENT_COLORS[i % AGENT_COLORS.length];
    const stColor = stateColor(a.status);
    const ns = 'http://www.w3.org/2000/svg';
    const wps = a.waypoints || [];
    if (wps.length > 1) {
      const poly = document.createElementNS(ns, 'polyline');
      poly.setAttribute('points', wps.map((p) => `${p.x},${p.y}`).join(' '));
      poly.setAttribute('class', 'route');
      poly.setAttribute('stroke', color);
      poly.setAttribute('data-tip', `${a.agent_id} 路线`);
      frag.appendChild(poly);
    }
    const pos = a.position;
    if (pos) {
      const dot = document.createElementNS(ns, 'circle');
      dot.setAttribute('cx', pos.x);
      dot.setAttribute('cy', pos.y);
      dot.setAttribute('r', '7');
      dot.setAttribute('class', 'agent-dot');
      dot.setAttribute('fill', stColor);
      dot.setAttribute('stroke', '#FFFFFF');
      dot.setAttribute('stroke-width', '2.5');
      dot.setAttribute('data-tip', `${a.agent_id} · ${a.status} · (${Math.round(pos.x)}, ${Math.round(pos.y)})`);
      frag.appendChild(dot);
    }
  });
  map.appendChild(frag);
  bindTooltip('#map');
}

function renderAgents() {
  if (!lastRan) return;
  const ran = lastRan;
  const wrap = document.getElementById('agent-cards');
  const states = ran.agent_states || [];
  const services = ran.service_states || [];
  const roleMap = t('agent.roleMap');
  wrap.innerHTML = '';
  for (const a of states) {
    const svc = services.find((s) => s.agent_id === a.agent_id && s.status && s.status !== 'COMPLETED' && s.status !== 'FAILED')
      || services.find((s) => s.agent_id === a.agent_id);
    const role = String(a.agent_id).split('_')[0] || 'agent';
    const stColor = stateColor(a.status);
    const ratio = svc && svc.progress ? (svc.progress.completion_ratio || 0) : 0;
    const dir = svc && svc.direction === 'DL' ? ' ↓' : svc && svc.direction === 'UL' ? ' ↑' : '';
    const card = document.createElement('div');
    card.className = 'agent-card';
    const pos = a.position ? `(${Math.round(a.position.x)}, ${Math.round(a.position.y)})` : '-';
    card.innerHTML = `
      <div class="head">
        <div class="avatar ${role === 'teacher' ? 'teacher' : role === 'staff' ? 'staff' : ''}">${a.agent_id[0].toUpperCase()}</div>
        <div class="name">${a.agent_id}</div>
        <span class="state-chip" style="background:${stColor}1A;color:${stColor}">${a.status || '-'}</span>
      </div>
      <div class="rows">
        <div><span class="k">${t('agent.pos')}</span> <span class="v">${pos}</span></div>
        <div><span class="k">${t('agent.dest')}</span> <span class="v">${a.target || '-'}</span></div>
        <div><span class="k">${t('agent.intent')}</span> <span class="v">${intentLabel(a.intent, svc)}${dir}</span></div>
        <div><span class="k">${t('agent.cp')}</span> <span class="v">${a.cm_state || '-'} · ${a.rrc_state || '-'}</span></div>
        <div><span class="k">${t('agent.path')}</span> <span class="v">${svc ? svc.service_instance_id : '-'}</span></div>
        <div><span class="k">${t('agent.role')}</span> <span class="v">${roleMap[role] || role}</span></div>
      </div>
      ${a.error ? `<div class="error-line">${t('agent.error')}: ${a.error}</div>` : ''}
      <div class="progress-track"><div class="progress-fill" style="width:${(ratio * 100).toFixed(1)}%;background:${stColor}"></div></div>`;
    wrap.append(card);
  }
}

/* ================= 图表(真实指标聚合) ================= */
const CHART_COLORS = { primary: '#4A87BE', tertiary: '#7D8CA4', secondary: '#5E7894', green: '#4C9E74', amber: '#B08A3E' };
function chartOpts() {
  return {
    responsive: true, maintainAspectRatio: false, animation: { duration: 250, easing: 'easeOutQuart' },
    plugins: {
      legend: { display: true, labels: { color: '#46525F', font: { size: 10 } } },
      tooltip: { enabled: true, backgroundColor: '#1D1B20', titleColor: '#E6E0E9', bodyColor: '#E6E0E9' },
    },
    scales: {
      x: { ticks: { display: false }, grid: { display: false } },
      y: { ticks: { display: false }, grid: { color: '#E2E9F2' }, border: { display: false } },
    },
  };
}
/* Chart.js 可能加载失败(CDN 不可达):图表可选,不阻塞 banner/卡片/地图 */
const charts = {};
function initCharts() {
  if (!window.CHART_OK) {
    document.querySelectorAll('.chart-card canvas').forEach((c) => { c.remove(); });
    return;
  }
  charts.throughput = new Chart(document.getElementById('ch-throughput'), {
    type: 'line',
    data: { labels: [], datasets: [
      { label: '', data: [], borderColor: CHART_COLORS.primary, backgroundColor: 'rgba(74,135,190,.12)', fill: true, tension: .35, pointRadius: 0, borderWidth: 2 },
      { label: '', data: [], borderColor: CHART_COLORS.tertiary, backgroundColor: 'rgba(125,140,164,.12)', fill: true, tension: .35, pointRadius: 0, borderWidth: 2 },
    ] },
    options: chartOpts(),
  });
  charts.prb = new Chart(document.getElementById('ch-prb'), {
    type: 'bar',
    data: { labels: [], datasets: [
      { label: '', data: [], backgroundColor: CHART_COLORS.primary, borderRadius: 4, borderSkipped: false },
    ] },
    options: chartOpts(),
  });
  charts.mcs = new Chart(document.getElementById('ch-mcs'), {
    type: 'bar',
    data: { labels: [], datasets: [
      { label: '', data: [], backgroundColor: CHART_COLORS.secondary, borderRadius: 4, borderSkipped: false },
    ] },
    options: chartOpts(),
  });
  charts.sinr = new Chart(document.getElementById('ch-sinr'), {
    type: 'line',
    data: { labels: [], datasets: [
      { label: '', data: [], borderColor: CHART_COLORS.green, tension: .35, pointRadius: 0, borderWidth: 2 },
      { label: '', data: [], borderColor: CHART_COLORS.amber, yAxisID: 'y1', tension: .35, pointRadius: 0, borderWidth: 2 },
    ] },
    options: { ...chartOpts(), scales: { ...chartOpts().scales, y1: { position: 'right', ticks: { display: false }, grid: { display: false }, border: { display: false } } } },
  });
}
function updateChartLabels() {
  if (!charts.throughput) return;
  charts.throughput.data.datasets[0].label = t('chart.ul');
  charts.throughput.data.datasets[1].label = t('chart.dl');
  charts.prb.data.datasets[0].label = t('chart.prbLabel');
  charts.mcs.data.datasets[0].label = t('chart.mcsLabel');
  charts.sinr.data.datasets[0].label = t('chart.snrLabel');
  charts.sinr.data.datasets[1].label = t('chart.delayLabel');
}

function aggregateTick(ran) {
  const services = ran.service_states || [];
  let ulBytes = 0, dlBytes = 0, prbs = 0, mcsSum = 0, sinrSum = 0, delaySum = 0, n = 0, nMcs = 0, nSinr = 0, nDelay = 0;
  for (const s of services) {
    const tx = s.transmission || {};
    if (s.direction === 'DL') dlBytes += tx.successful_bytes || 0;
    else ulBytes += tx.successful_bytes || 0;
    const alloc = s.allocation || {};
    prbs += alloc.prbs || 0;
    if (alloc.mcs !== undefined) { mcsSum += alloc.mcs; nMcs++; }
    const ch = s.channel || {};
    if (ch.sinr_db !== undefined && ch.sinr_db !== null) { sinrSum += ch.sinr_db; nSinr++; }
    const n3 = s.n3 || {}, n6 = s.n6 || {};
    if (n3.n3_delay_ms !== undefined || n6.n6_delay_ms !== undefined) { delaySum += (n3.n3_delay_ms || 0) + (n6.n6_delay_ms || 0); nDelay++; }
    n++;
  }
  series.ul.push(Math.round(ulBytes / 1024));
  series.dl.push(Math.round(dlBytes / 1024));
  series.prb.push(n > 0 ? Math.round((prbs / (106 * n)) * 100) : 0);
  series.mcs.push(nMcs > 0 ? Math.round(mcsSum / nMcs) : 0);
  series.sinr.push(nSinr > 0 ? +(sinrSum / nSinr).toFixed(1) : 0);
  series.delay.push(nDelay > 0 ? +(delaySum / nDelay).toFixed(1) : 0);
  const prog = ran.progress || {};
  series.delivered.push(prog.completion_ratio !== undefined ? Math.round(prog.completion_ratio * 100) : 0);
  for (const k in series) if (series[k].length > MAX_POINTS) series[k].shift();
}

function updateCharts() {
  if (!charts.throughput) return;
  const labels = series.ul.map((_, i) => `t${tick - series.ul.length + 1 + i}`);
  charts.throughput.data.labels = labels;
  charts.throughput.data.datasets[0].data = series.ul;
  charts.throughput.data.datasets[1].data = series.dl;
  charts.prb.data.labels = labels; charts.prb.data.datasets[0].data = series.prb;
  charts.mcs.data.labels = labels; charts.mcs.data.datasets[0].data = series.mcs;
  charts.sinr.data.labels = labels;
  charts.sinr.data.datasets[0].data = series.sinr;
  charts.sinr.data.datasets[1].data = series.delay;
  for (const k in charts) charts[k].update();
}

/* ================= 轮询与导出 ================= */
function setConnStatus(ok) {
  const el = document.getElementById('st-status');
  const dot = el.previousElementSibling;
  if (ok) {
    el.textContent = t('overview.running');
    dot.classList.add('running');
  } else {
    el.textContent = t('overview.waiting');
    dot.classList.remove('running');
  }
}
function poll() {
  fetch('/outputs/live_state.json', { cache: 'no-store' })
    .then((r) => (r.ok ? r.json() : null))
    .then((data) => {
      if (!data) {
        // 模拟启动间隙 / 切换写入瞬间可能短暂 404:静默重试,不刷屏
        emptyFetches++;
        if (emptyFetches === 1) console.info('[preview] 等待 live_state.json(模拟启动中或文件切换间隙)');
        setConnStatus(false);
        return;
      }
      const ran = data.ran_state || data;
      if (ran.tick === tick) return; // 无新 tick
      try {
        // 渲染链整体保护:任一步抛错都不推进 tick 标记,下次 poll 自动重试
        tick = ran.tick;
        lastRan = ran;
        aggregateTick(ran);
        updateBanner(ran, data.now_seconds);
        renderRoutes(ran);
        renderAgents();
        updateCharts();
        emptyFetches = 0;
        setConnStatus(true);
        lastUpdateAt = Date.now();
        const lu = document.getElementById('st-last');
        if (lu) lu.textContent = t('overview.updated') + ' ' + new Date(lastUpdateAt).toLocaleTimeString();
      } catch (err) {
        // 渲染异常:不提交 tick,保持旧状态,下个轮询重试(避免 tick 卡死)
        console.warn('[preview] 渲染异常(已跳过本 tick):', err);
      }
    })
    .catch((err) => {
      emptyFetches++;
      setConnStatus(false);
      if (emptyFetches === 1) console.warn('[preview] live_state 拉取失败(服务器未启动?):', err);
    });
}
document.getElementById('btn-pause').addEventListener('click', (e) => {
  paused = !paused;
  e.currentTarget.textContent = paused ? t('overview.resume') : t('overview.pause');
  if (!paused) poll();
});
document.getElementById('btn-export').addEventListener('click', () => {
  const blob = new Blob([JSON.stringify({ tick, series, service_states: lastRan ? lastRan.service_states : [] }, null, 2)],
    { type: 'application/json' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'simulation_logs.json';
  a.click();
});

applyI18n();
renderAgents();
function initChartsWhenReady() {
  if (window.CHART_OK === undefined) { setTimeout(initChartsWhenReady, 100); return; }
  initCharts();
  updateChartLabels();
}
initChartsWhenReady();
poll();
setInterval(() => { if (!paused) poll(); }, 500);
// 后台标签页 setInterval 会被浏览器节流:切回前台立即拉一次,不等下一个周期
document.addEventListener('visibilitychange', () => {
  if (!document.hidden && !paused) poll();
});

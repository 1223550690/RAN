/* ================= 国际化 ================= */
const I18N = {
  zh: {
    'overview.title': 'Simulation Overview',
    'overview.tick': 'tick', 'overview.agents': 'agents', 'overview.time': '用时',
    'overview.services': '活跃服务', 'overview.delivered': '交付', 'overview.running': '运行中',
    'overview.pause': '暂停', 'overview.resume': '继续', 'overview.export': '导出 Logs',
    'overview.waiting': '等待数据…', 'overview.updated': '更新', 'overview.paused': '已暂停',
    'map.hint': '悬停查看对象信息 · 浅色缺口 = 可通行',
    'map.heatmap': '信道热力图',
    'map.passable': '可通行', 'map.road': '大道', 'map.junction': '交汇', 'map.boundary': '边界',
    'chart.throughput': '系统吞吐量(UL/DL)', 'chart.prb': 'PRB 利用率', 'chart.mcs': 'MCS 分布',
    'chart.snr': '平均 SINR / QoS 时延',
    'agent.waiting': '等待意图提交 / 无 RAN 服务',
    'agent.pos': '位置', 'agent.dest': '目标', 'agent.intent': '意图', 'agent.cp': '控制面',
    'agent.path': '路径', 'agent.role': '角色', 'agent.error': '错误',
    'agent.roleMap': { student: '学生', teacher: '教师', staff: '职员' },
    'agent.intentMap': { message: '发送消息', video_upload: '上传视频', video_download: '下载视频', video_call: '视频通话', file_transfer: '传输文件' },
    'task.panel': '任务列表',
    'task.pending': '待执行',
    'chart.ul': 'UL KB/tick', 'chart.dl': 'DL KB/tick', 'chart.prbLabel': 'PRB 利用率 %',
    'chart.waiting': '等待 agent 到达目标并提交业务…(当前为移动阶段)',
    'chart.mcsLabel': 'MCS 档位', 'chart.snrLabel': 'SINR dB', 'chart.delayLabel': '时延 ms',
    'chart.snr': '每 UE SINR(dB)', 'chart.bler': '每 UE BLER(%)',
    'chart.delay': '每服务端到端时延(ms)', 'chart.congestion': '拥塞度(PRB 占用 / 队列积压)',
    'chart.congPrb': 'PRB 占用 %', 'chart.congQueue': '队列积压 KB', 'chart.completion': '服务完成进度(%)',
  },
  en: {
    'overview.title': 'Simulation Overview',
    'overview.tick': 'tick', 'overview.agents': 'agents', 'overview.time': 'elapsed',
    'overview.services': 'active services', 'overview.delivered': 'delivered', 'overview.running': 'running',
    'overview.pause': 'Pause', 'overview.resume': 'Resume', 'overview.export': 'Export Logs',
    'overview.waiting': 'Waiting for data…', 'overview.updated': 'Updated', 'overview.paused': 'Paused',
    'map.hint': 'Hover for details · light gap = passable',
    'map.passable': 'passable', 'map.road': 'road', 'map.junction': 'junction', 'map.boundary': 'boundary',
    'chart.throughput': 'Throughput (UL/DL)', 'chart.prb': 'PRB Utilization', 'chart.mcs': 'MCS Distribution',
    'chart.snr': 'Avg SINR / QoS Delay',
    'agent.waiting': 'Waiting for intent / no RAN service',
    'agent.pos': 'Position', 'agent.dest': 'Target', 'agent.intent': 'Intent', 'agent.cp': 'Control plane',
    'agent.path': 'Path', 'agent.role': 'Role', 'agent.error': 'Error',
    'agent.roleMap': { student: 'Student', teacher: 'Teacher', staff: 'Staff' },
    'agent.intentMap': { message: 'Send message', video_upload: 'Upload video', video_download: 'Download video', video_call: 'Video call', file_transfer: 'Transfer file' },
    'task.panel': 'Task list',
    'task.pending': 'Pending',
    'chart.ul': 'UL KB/tick', 'chart.dl': 'DL KB/tick', 'chart.prbLabel': 'PRB util %',
    'chart.waiting': 'Waiting for agents to reach targets and submit traffic… (movement phase)',
    'chart.mcsLabel': 'MCS level', 'chart.snrLabel': 'SINR dB', 'chart.delayLabel': 'Delay ms',
    'chart.snr': 'Per-UE SINR(dB)', 'chart.bler': 'Per-UE BLER(%)',
    'chart.delay': 'Per-service E2E delay(ms)', 'chart.congestion': 'Congestion (PRB util / queue)',
    'chart.congPrb': 'PRB util %', 'chart.congQueue': 'Queue backlog KB', 'chart.completion': 'Service completion(%)',
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
const trails = {}; // agent 移动轨迹(页面本地累积)
let tick = -1; // 初始 -1:保证首次 poll(文件 tick 0 或 80)必然通过 early-return 守卫并渲染
let emptyFetches = 0;
const MAX_POINTS = 60;
const series = { ul: [], dl: [], prb: [], mcs: [], sinr: [], delay: [], delivered: [] };
/* 每 UE / 每服务动态序列(多线图数据源) */
const perUe = {};   // { ue_id: { sinr: [...], bler: [...] } }
const perSvc = {};  // { service_instance_id: { delay: [...], ratio: [...] } }
const cong = { prb: [], queue: [], waiting: [] };
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

  // 重建地图内容;热力图 <image> 是独立子元素,清空后需重挂
  svg.innerHTML = parts.join('\n');
  if (heatmapImage) {
    svg.appendChild(heatmapImage); // 最后追加:保持在最上层(半透明叠加)
  }

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
/* ================= CKM 热力图叠加 ================= */
/* 离屏 Canvas 绘制 → dataURL → SVG <image> 子元素:
   热力图与建筑/墙/道路共用 SVG viewBox 变换(xMidYMid meet 等比+居中),
   任何浏览器缩放/窗口尺寸下天然对齐,无需手动计算偏移。 */
let heatmapImage = null;
function rsrpColor(rsrp, lo, hi) {
  // 自适应色阶:lo(红)→ hi(绿),数据范围归一化
  const t = hi > lo ? Math.max(0, Math.min(1, (rsrp - lo) / (hi - lo))) : 0.5;
  return `hsl(${(t * 120).toFixed(0)}, 75%, 45%)`;
}
function ensureHeatmapImage() {
  if (heatmapImage) return heatmapImage;
  const svg = document.getElementById('map');
  if (!svg) return null;
  heatmapImage = document.createElementNS('http://www.w3.org/2000/svg', 'image');
  heatmapImage.setAttribute('id', 'heatmap-img');
  heatmapImage.setAttribute('x', '0');
  heatmapImage.setAttribute('y', '0');
  heatmapImage.setAttribute('width', '2000');
  heatmapImage.setAttribute('height', '2000');
  heatmapImage.setAttribute('preserveAspectRatio', 'none'); // 2000x2000 与 viewBox 一致,无变形
  heatmapImage.style.pointerEvents = 'none';
  svg.appendChild(heatmapImage); // 最后追加:绘制在地图内容之上(半透明)
  return heatmapImage;
}
function loadHeatmap() {
  fetch('/outputs/ckm_heatmap_bristol_topology.json?ts=' + Date.now(), { cache: 'no-store' })
    .then((r) => (r.ok ? r.json() : null))
    .then((data) => {
      if (!data || !Array.isArray(data.points) || !data.points.length) return;
      const img = ensureHeatmapImage();
      if (!img) return;
      // 自适应色阶:按数据实际分布取 2%~98% 分位(抗离群点)
      const vals = data.points.map((p) => p.rsrp).sort((a, b) => a - b);
      const q = (k) => vals[Math.min(vals.length - 1, Math.floor(k * (vals.length - 1)))];
      const lo = q(0.02), hi = q(0.98);
      // 离屏 Canvas 2000x2000(与地图坐标 1:1)
      const canvas = document.createElement('canvas');
      canvas.width = 2000;
      canvas.height = 2000;
      const ctx = canvas.getContext('2d');
      const scale = data.grid_scale_m || 25;
      for (const p of data.points) {
        ctx.fillStyle = rsrpColor(p.rsrp, lo, hi);
        ctx.fillRect(p.x, p.y, scale, scale);
      }
      img.setAttribute('href', canvas.toDataURL('image/png'));
      img.setAttribute('xlink:href', img.getAttribute('href')); // 兼容旧浏览器
      // 保险:若已被 renderMap 重建清出 DOM,重挂(保持最上层)
      if (!img.isConnected) document.getElementById('map')?.appendChild(img);
      img.classList.add('visible');
      const legend = document.querySelector('.heatmap-legend');
      if (legend) {
        legend.querySelector('.labels span:first-child').textContent = lo.toFixed(0) + ' dBm';
        legend.querySelector('.labels span:last-child').textContent = hi.toFixed(0) + ' dBm';
        legend.classList.add('visible');
      }
    })
    .catch(() => {});
}
function toggleHeatmap(show) {
  const img = ensureHeatmapImage();
  if (!img) return;
  img.classList.toggle('visible', show);
  document.querySelector('.heatmap-legend')?.classList.toggle('visible', show);
  localStorage.setItem('preview-heatmap', show ? '1' : '0');
}
document.getElementById('btn-heatmap')?.addEventListener('click', (e) => {
  const img = ensureHeatmapImage();
  const on = img ? !img.classList.contains('visible') : true;
  toggleHeatmap(on);
});

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
  map.querySelectorAll('.route, .agent-dot, .agent-trail').forEach((el) => el.remove());
  const states = ran.agent_states || [];
  const frag = document.createDocumentFragment();
  states.forEach((a, i) => {
    const color = AGENT_COLORS[i % AGENT_COLORS.length];
    const stColor = stateColor(a.status);
    const ns = 'http://www.w3.org/2000/svg';
    // 轨迹:页面本地累积的移动历史(打开页面即可见"在动")
    const pos = a.position;
    if (pos) {
      const trail = (trails[a.agent_id] = trails[a.agent_id] || []);
      if (!trail.length || Math.abs(trail[trail.length - 1].x - pos.x) > 1 || Math.abs(trail[trail.length - 1].y - pos.y) > 1) {
        trail.push({ x: pos.x, y: pos.y });
        if (trail.length > 300) trail.shift();
      }
      if (trail.length > 1) {
        const tr = document.createElementNS(ns, 'polyline');
        tr.setAttribute('points', trail.map((p) => `${p.x},${p.y}`).join(' '));
        tr.setAttribute('class', 'agent-trail');
        tr.setAttribute('stroke', color);
        tr.setAttribute('data-tip', `${a.agent_id} 移动轨迹`);
        frag.appendChild(tr);
      }
    }
    // 规划路线(waypoints 完整路径,PLANNING 完成后出现)
    const wps = a.waypoints || [];
    if (wps.length > 1) {
      const poly = document.createElementNS(ns, 'polyline');
      poly.setAttribute('points', wps.map((p) => `${p.x},${p.y}`).join(' '));
      poly.setAttribute('class', 'route');
      poly.setAttribute('stroke', color);
      poly.setAttribute('data-tip', `${a.agent_id} 规划路线`);
      frag.appendChild(poly);
    }
    // 实时位置点
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

/* 任务面板(右上 state 栏):模板模式的简要任务列表 + 实时进度。
   plan_summary = 静态任务清单(agent_id/intent_type/direction/index/total);
   动态进度按提交顺序与 ran_state.service_states 对齐。 */
function renderTaskPanel(planSummary, ran) {
  const panel = document.getElementById('task-panel');
  const list = document.getElementById('task-list');
  if (!panel || !list) return;
  if (!planSummary || !planSummary.length) { panel.style.display = 'none'; return; }
  panel.style.display = 'block';
  const services = ran.service_states || [];
  const byAgent = {};
  for (const p of planSummary) (byAgent[p.agent_id] || (byAgent[p.agent_id] = [])).push(p);
  const labels = (I18N[lang]['agent.intentMap'] || {});
  const pendingLabel = I18N[lang]['task.pending'] || '待执行';
  let html = '';
  for (const [agentId, tasks] of Object.entries(byAgent)) {
    const svcs = services.filter((s) => s.agent_id === agentId);
    html += `<div class="task-group"><div class="tg-head"><div class="avatar">${String(agentId)[0].toUpperCase()}</div>${agentId}</div>`;
    tasks.forEach((task, idx) => {
      const svc = svcs[idx]; // 提交顺序对齐
      const kind = String(task.intent_type).replace(/_\d+$/, '');
      const label = labels[kind] || task.intent_type;
      const icon = task.direction === 'DL' ? '↓' : '↑';
      const multi = tasks.length > 1 ? ` ${idx + 1}/${tasks.length}` : '';
      let pct = 0, cls = 'pending', barCls = '';
      if (svc) {
        const ratio = svc.progress && svc.progress.completion_ratio != null ? svc.progress.completion_ratio : 0;
        pct = Math.round(ratio * 100);
        if (svc.status === 'COMPLETED') { pct = 100; barCls = 'done'; cls = ''; }
        else if (svc.status === 'ACTIVE' || svc.status === 'WAITING_FOR_ALLOCATION') cls = '';
      }
      const pctText = cls === 'pending' ? pendingLabel : pct + '%';
      html += `<div class="task-row ${cls}"><span class="t-icon">${icon}</span><span class="t-name">${label}${multi}</span><div class="t-bar"><div class="t-fill ${barCls}" style="width:${pct}%"></div></div><span class="t-pct">${pctText}</span></div>`;
    });
    html += '</div>';
  }
  list.innerHTML = html;
}

/* ================= 图表(真实指标聚合) ================= */
const CHART_COLORS = { primary: '#4A87BE', tertiary: '#7D8CA4', secondary: '#5E7894', green: '#4C9E74', amber: '#B08A3E' };
function chartOpts() {
  return {
    responsive: true, maintainAspectRatio: false, animation: { duration: 250, easing: 'easeOutQuart' },
    plugins: {
      legend: { display: true, labels: { color: '#46525F', font: { size: 10 } } },
      tooltip: {
        enabled: true, backgroundColor: '#1D1B20', titleColor: '#E6E0E9', bodyColor: '#E6E0E9',
        callbacks: {
          // 悬停显示:数据集名(UE/服务/方向)+ 数值 + 单位
          label: (ctx) => {
            const ds = ctx.dataset || {};
            const v = ctx.parsed && ctx.parsed.y !== undefined && ctx.parsed.y !== null ? ctx.parsed.y : '-';
            return `${ds.label || ''}: ${v}${ds.unit || ''}`;
          },
        },
      },
    },
    scales: {
      x: { ticks: { display: false }, grid: { display: false } },
      y: { ticks: { display: false }, grid: { color: '#E2E9F2' }, border: { display: false } },
    },
  };
}
/* Chart.js 可能加载失败(CDN 不可达):图表可选,不阻塞 banner/卡片/地图 */
const charts = {};
/* 图表类型注册表(下拉切换;单 canvas 复用,避免隐藏容器 Chart.js 尺寸问题) */
const CHART_KINDS = [
  { id: 'throughput', zh: '系统吞吐量(UL/DL)', en: 'Throughput (UL/DL)' },
  { id: 'prb', zh: 'PRB 利用率', en: 'PRB utilisation' },
  { id: 'mcs', zh: 'MCS 分布', en: 'MCS distribution' },
  { id: 'sinr', zh: '每 UE SINR(dB)', en: 'Per-UE SINR(dB)' },
  { id: 'bler', zh: '每 UE BLER(%)', en: 'Per-UE BLER(%)' },
  { id: 'delay', zh: '每服务端到端时延(ms)', en: 'Per-service E2E delay(ms)' },
  { id: 'congestion', zh: '拥塞度(PRB 占用 / 队列积压)', en: 'Congestion (PRB util / queue)' },
  { id: 'completion', zh: '服务完成进度(%)', en: 'Service completion(%)' },
];
let chartKind = 'throughput';

function chartKindLabel(id) {
  const k = CHART_KINDS.find((c) => c.id === id);
  return k ? (lang === 'zh' ? k.zh : k.en) : id;
}

/* 按类型构建图表数据(labels + datasets + 可选双轴配置) */
function buildChartData(kind) {
  const labels = series.ul.map((_, i) => `t${tick - series.ul.length + 1 + i}`);
  const ueIds = Object.keys(perUe).sort();
  const svcIds = Object.keys(perSvc).sort();
  switch (kind) {
    case 'throughput':
      return { type: 'line', labels, datasets: [
        { label: t('chart.ul'), data: series.ul, borderColor: CHART_COLORS.primary, backgroundColor: 'rgba(74,135,190,.12)', fill: true, tension: .35, pointRadius: 0, borderWidth: 2, unit: ' KB' },
        { label: t('chart.dl'), data: series.dl, borderColor: CHART_COLORS.tertiary, backgroundColor: 'rgba(125,140,164,.12)', fill: true, tension: .35, pointRadius: 0, borderWidth: 2, unit: ' KB' },
      ] };
    case 'prb':
      return { type: 'bar', labels, datasets: [
        { label: t('chart.prbLabel'), data: series.prb, backgroundColor: CHART_COLORS.primary, borderRadius: 4, borderSkipped: false, unit: ' %' },
      ] };
    case 'mcs':
      return { type: 'bar', labels, datasets: [
        { label: t('chart.mcsLabel'), data: series.mcs, backgroundColor: CHART_COLORS.secondary, borderRadius: 4, borderSkipped: false, unit: '' },
      ] };
    case 'sinr':
      return { type: 'line', labels, datasets: ueIds.map((ue, i) => ({
        label: ue, data: perUe[ue].sinr, borderColor: AGENT_COLORS[i % AGENT_COLORS.length],
        tension: .35, pointRadius: 0, borderWidth: 2, spanGaps: true, unit: ' dB',
      })) };
    case 'bler':
      return { type: 'line', labels, datasets: ueIds.map((ue, i) => ({
        label: ue, data: perUe[ue].bler, borderColor: AGENT_COLORS[(i + 2) % AGENT_COLORS.length],
        tension: .35, pointRadius: 0, borderWidth: 2, spanGaps: true, unit: ' %',
      })) };
    case 'delay':
      return { type: 'line', labels, datasets: svcIds.map((sid, i) => ({
        label: perSvc[sid].label || sid, data: perSvc[sid].delay,
        borderColor: AGENT_COLORS[(i + 1) % AGENT_COLORS.length],
        tension: .35, pointRadius: 0, borderWidth: 2, spanGaps: true, unit: ' ms',
      })) };
    case 'congestion':
      return { type: 'line', labels, y1: true, datasets: [
        { label: t('chart.congPrb'), data: cong.prb, borderColor: CHART_COLORS.primary, tension: .35, pointRadius: 0, borderWidth: 2, yAxisID: 'y', unit: ' %' },
        { label: t('chart.congQueue'), data: cong.queue, borderColor: CHART_COLORS.amber, tension: .35, pointRadius: 0, borderWidth: 2, yAxisID: 'y1', unit: ' KB' },
      ] };
    case 'completion':
      return { type: 'bar', labels: svcIds.map((sid) => perSvc[sid].label || sid), datasets: [{
        label: t('chart.completion'), data: svcIds.map((sid) => perSvc[sid].ratio[perSvc[sid].ratio.length - 1] || 0),
        backgroundColor: svcIds.map((_, i) => AGENT_COLORS[i % AGENT_COLORS.length] + 'CC'),
        borderRadius: 4, borderSkipped: false, unit: ' %',
      }] };
    default:
      return { type: 'line', labels, datasets: [] };
  }
}

function chartOptionsFor(kind) {
  const opts = chartOpts();
  if (kind === 'congestion') {
    opts.scales = { ...opts.scales, y1: { position: 'right', ticks: { display: false }, grid: { display: false }, border: { display: false } } };
  }
  return opts;
}

function rebuildMainChart() {
  if (charts.main) { charts.main.destroy(); charts.main = null; }
  if (!window.CHART_OK) return;
  const data = buildChartData(chartKind);
  charts.main = new Chart(document.getElementById('ch-main'), {
    type: data.type,
    data: { labels: data.labels, datasets: data.datasets },
    options: chartOptionsFor(chartKind),
  });
}

function initCharts() {
  const sel = document.getElementById('chart-select');
  if (sel) {
    sel.innerHTML = CHART_KINDS.map((k) => `<option value="${k.id}">${lang === 'zh' ? k.zh : k.en}</option>`).join('');
    sel.value = chartKind;
    sel.addEventListener('change', (e) => { chartKind = e.target.value; rebuildMainChart(); });
  }
  if (!window.CHART_OK) {
    document.querySelectorAll('.chart-card canvas').forEach((c) => { c.remove(); });
    return;
  }
  rebuildMainChart();
}
function updateChartLabels() {
  const sel = document.getElementById('chart-select');
  if (sel) {
    Array.from(sel.options).forEach((opt) => { opt.textContent = chartKindLabel(opt.value); });
  }
  if (charts.main) charts.main.destroy();
  charts.main = null;
  rebuildMainChart();
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

  // ---- 每 UE / 每服务动态序列(多线图) ----
  const seenUe = new Set(), seenSvc = new Set();
  for (const s of services) {
    const tx = s.transmission || {}, ch = s.channel || {}, n3 = s.n3 || {}, n6 = s.n6 || {};
    const ue = s.ue_id || s.agent_id || 'ue';
    seenUe.add(ue);
    if (!perUe[ue]) perUe[ue] = { sinr: [], bler: [] };
    perUe[ue].sinr.push(ch.sinr_db !== undefined && ch.sinr_db !== null ? +ch.sinr_db.toFixed(1) : null);
    const attempted = tx.attempted_bytes || 0, failed = tx.failed_bytes || 0;
    perUe[ue].bler.push(attempted > 0 ? +((failed / attempted) * 100).toFixed(2) : null);
    const sid = s.service_instance_id || s.intent_id || `${ue}_svc`;
    seenSvc.add(sid);
    if (!perSvc[sid]) perSvc[sid] = { delay: [], ratio: [], label: `${ue} ${s.direction || ''}` };
    const delayMs = (n3.n3_delay_ms || 0) + (n6.n6_delay_ms || 0);
    perSvc[sid].delay.push(delayMs > 0 ? +delayMs.toFixed(2) : null);
    const ratio = s.progress && s.progress.completion_ratio != null ? s.progress.completion_ratio : 0;
    perSvc[sid].ratio.push(Math.round(ratio * 100));
  }
  // 未出现的新 UE/服务补齐 null(保持线长一致);已消失的删除
  for (const ue of Object.keys(perUe)) {
    if (perUe[ue].sinr.length < series.ul.length) { perUe[ue].sinr.push(null); perUe[ue].bler.push(null); }
    if (!seenUe.has(ue)) delete perUe[ue];
  }
  for (const sid of Object.keys(perSvc)) {
    if (perSvc[sid].delay.length < series.ul.length) { perSvc[sid].delay.push(null); perSvc[sid].ratio.push(null); }
    if (!seenSvc.has(sid)) delete perSvc[sid];
  }
  for (const k of Object.keys(perUe)) for (const f of ['sinr', 'bler']) if (perUe[k][f].length > MAX_POINTS) perUe[k][f].shift();
  for (const k of Object.keys(perSvc)) for (const f of ['delay', 'ratio']) if (perSvc[k][f].length > MAX_POINTS) perSvc[k][f].shift();

  // ---- 拥塞度(顶层) ----
  const c = ran.congestion || {};
  cong.prb.push(c.prb_ratio !== undefined ? Math.round(c.prb_ratio * 100) : 0);
  cong.queue.push(c.queue_bytes !== undefined ? Math.round(c.queue_bytes / 1024) : 0); // KB
  cong.waiting.push(c.waiting_ticks || 0);

  for (const k in series) if (series[k].length > MAX_POINTS) series[k].shift();
  for (const k in cong) if (cong[k].length > MAX_POINTS) cong[k].shift();
}

function updateCharts() {
  if (!charts.main) {
    // Chart.js(CDN)/initCharts 尚未就绪:自排队重试,避免首次 poll 早于
    // 图表初始化而被永久跳过(文件静止时 tick 不再变化,外部不会再触发)
    setTimeout(updateCharts, 300);
    return;
  }
  // 空态切换:无业务数据时显示等待提示(系列长度>0 即渲染,避免首次 poll
  // 数据为 0 时被守卫拦下、文件静止后永不重绘)
  const hasData = series.ul.length > 0 || series.dl.length > 0;
  document.querySelectorAll('.chart-empty').forEach((el) => {
    el.style.display = hasData ? 'none' : 'flex';
  });
  if (!hasData) return;
  // 单图更新:按当前下拉类型重建数据(不销毁实例,保持交互)
  const data = buildChartData(chartKind);
  charts.main.data.labels = data.labels;
  charts.main.data.datasets = data.datasets;
  charts.main.update();
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
  // URL 加时间戳:Chrome 对无缓存头响应的启发式缓存/条件请求会返回旧副本
  // (页面静止、后台数据在动的根因),时间戳参数保证每次都是真实请求
  fetch('/outputs/live_state.json?ts=' + Date.now(), { cache: 'no-store' })
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
      // 合并顶层实时 Agent 状态(移动/生命周期),ran 侧保留控制面字段。
      // 顶层 data.agents 是 Agent 子系统权威实时状态;ran_state.agent_states
      // 是 RAN 场景副本(无活跃业务时曾停止刷新),以顶层为准避免移动冻结。
      // 注意:顶层 position/waypoints 是数组 [x,y],需归一化为 {x,y}。
      const normPt = (v) => (Array.isArray(v) && v.length >= 2 ? { x: v[0], y: v[1] } : v);
      if (Array.isArray(data.agents) && data.agents.length) {
        const top = new Map(data.agents.map((a) => [a.agent_id, a]));
        ran.agent_states = (ran.agent_states || []).map((s) => {
          const t = top.get(s.agent_id);
          if (!t) return s;
          const m = Object.assign({}, s);
          if (t.lifecycle_status !== undefined) m.status = t.lifecycle_status;
          if (t.position !== undefined) m.position = normPt(t.position);
          if (t.waypoints !== undefined) m.waypoints = Array.isArray(t.waypoints) ? t.waypoints.map(normPt) : t.waypoints;
          for (const f of ['waypoint_index', 'waypoint_count', 'current_room_id', 'destination_id', 'current_intent_id', 'activity_state', 'error', 'last_transition_tick']) {
            if (t[f] !== undefined) m[f] = t[f];
          }
          return m;
        });
      }
      if (ran.tick === tick) return; // 无新 tick
      // 渲染链:单步失败不阻塞其余更新,tick 照常推进(不能因渲染问题卡停)
      const safe = (fn, name) => {
        try { fn(); } catch (e) { console.warn('[preview] 渲染异常(' + name + '):', e); }
      };
      tick = ran.tick;
      lastRan = ran;
      safe(() => aggregateTick(ran), 'aggregateTick');
      safe(() => updateBanner(ran, data.now_seconds), 'updateBanner');
      safe(() => renderRoutes(ran), 'renderRoutes');
      safe(() => renderAgents(), 'renderAgents');
      safe(() => renderTaskPanel(data.plan_summary || [], ran), 'renderTaskPanel');
      safe(() => updateCharts(), 'updateCharts');
      emptyFetches = 0;
      setConnStatus(true);
      lastUpdateAt = Date.now();
      const lu = document.getElementById('st-last');
      if (lu) lu.textContent = t('overview.updated') + ' ' + new Date(lastUpdateAt).toLocaleTimeString();
    })
    .catch((err) => {
      emptyFetches++;
      setConnStatus(false);
      if (emptyFetches === 1) console.warn('[preview] live_state 拉取失败(服务器未启动?):', err);
    });
}
/* 暂停按钮:真暂停后台模拟(控制文件通道);服务器不支持时降级为本地冻结 */
document.getElementById('btn-pause').addEventListener('click', async (e) => {
  const btn = e.currentTarget;
  const nextPaused = !paused;
  try {
    const resp = await fetch('/api/simulation/control?action=toggle&ts=' + Date.now(), { method: 'POST' });
    const data = await resp.json();
    if (data && data.ok) {
      // 后台真暂停/恢复:页面继续轮询(暂停时 tick 不再变化,显示最后数据)
      paused = nextPaused;
      btn.textContent = paused ? t('overview.resume') : t('overview.pause');
      const st = document.getElementById('st-status');
      if (st) st.textContent = paused ? t('overview.paused') : t('overview.running');
      return;
    }
    throw new Error(data && data.error ? data.error : 'control api failed');
  } catch (err) {
    // 纯静态服务器(无控制 API):降级为本地冻结视图
    paused = nextPaused;
    btn.textContent = paused ? t('overview.resume') : t('overview.pause');
    console.warn('[preview] 服务器不支持后台暂停,已切换为仅冻结视图:', err);
    if (!paused) poll();
  }
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
loadHeatmap();
toggleHeatmap(localStorage.getItem('preview-heatmap') !== '0');
poll();
setInterval(() => { if (!paused) poll(); }, 500);
// 后台标签页 setInterval 会被浏览器节流:切回前台立即拉一次,不等下一个周期
document.addEventListener('visibilitychange', () => {
  if (!document.hidden && !paused) poll();
});

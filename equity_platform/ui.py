from __future__ import annotations

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Equity Platform — Relationship Graph</title>
<style>
  :root {
    --bg: #0d1117; --panel: #161b22; --border: #30363d; --text: #e6edf3;
    --muted: #8b949e; --accent: #58a6ff;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--text); font: 14px/1.45 -apple-system, "Segoe UI", Roboto, sans-serif; }
  header { display: flex; align-items: center; gap: 16px; padding: 12px 20px; border-bottom: 1px solid var(--border); }
  header h1 { font-size: 16px; font-weight: 600; }
  header .pill { font-size: 12px; padding: 2px 10px; border-radius: 999px; border: 1px solid var(--border); color: var(--muted); }
  header .pill.ok { color: #3fb950; border-color: #238636; }
  .layout { display: grid; grid-template-columns: 1fr 340px; gap: 0; height: calc(100vh - 47px); }
  #canvas-wrap { position: relative; overflow: hidden; }
  canvas { display: block; width: 100%; height: 100%; cursor: grab; }
  .legend { position: absolute; left: 14px; bottom: 14px; background: var(--panel); border: 1px solid var(--border); border-radius: 8px; padding: 10px 14px; font-size: 12px; color: var(--muted); }
  .legend .row { display: flex; align-items: center; gap: 8px; margin: 3px 0; }
  .legend .swatch { width: 18px; height: 3px; border-radius: 2px; }
  .legend .node { width: 10px; height: 10px; border-radius: 50%; }
  .tooltip { position: absolute; pointer-events: none; background: var(--panel); border: 1px solid var(--border); border-radius: 6px; padding: 8px 10px; font-size: 12px; display: none; max-width: 280px; z-index: 5; }
  .side { border-left: 1px solid var(--border); overflow-y: auto; padding: 14px; display: flex; flex-direction: column; gap: 14px; }
  .card { background: var(--panel); border: 1px solid var(--border); border-radius: 8px; padding: 12px; }
  .card h2 { font-size: 12px; text-transform: uppercase; letter-spacing: .06em; color: var(--muted); margin-bottom: 10px; }
  .queue-item { padding: 8px 0; border-bottom: 1px solid var(--border); }
  .queue-item:last-child { border-bottom: none; }
  .queue-item .head { display: flex; justify-content: space-between; gap: 8px; }
  .queue-item .score { color: var(--accent); font-variant-numeric: tabular-nums; }
  .tag { display: inline-block; font-size: 11px; padding: 1px 7px; border-radius: 4px; margin-right: 6px; }
  .tag.material { background: #da363334; color: #f85149; }
  .tag.relevant { background: #bb800933; color: #d29922; }
  .tag.noise { background: #30363d; color: var(--muted); }
  .ticker-chip { display: inline-block; font-weight: 700; font-size: 12px; color: var(--accent); margin-right: 6px; }
  .muted { color: var(--muted); font-size: 12px; }
</style>
</head>
<body>
<header>
  <h1>Equity Platform</h1>
  <span class="pill" id="health">loading…</span>
  <span class="pill" id="edge-count"></span>
  <span class="pill">drag nodes · click to focus · double-click to reset</span>
</header>
<div class="layout">
  <div id="canvas-wrap">
    <canvas id="graph"></canvas>
    <div class="legend" id="legend"></div>
    <div class="tooltip" id="tooltip"></div>
  </div>
  <aside class="side">
    <div class="card"><h2>Triage queue</h2><div id="queue"><span class="muted">loading…</span></div></div>
    <div class="card"><h2>Watchlist</h2><div id="watchlist" class="muted">loading…</div></div>
  </aside>
</div>
<script>
const EDGE_COLORS = {
  competitor: "#f85149", supplier: "#a371f7", customer: "#3fb950",
  peer_group: "#58a6ff", shared_catalyst: "#d29922", correlation: "#8b949e",
};
const EDGE_LABELS = {
  competitor: "competitor", supplier: "supplier", customer: "customer",
  peer_group: "peer group", shared_catalyst: "shared catalyst", correlation: "correlation",
};

const canvas = document.getElementById("graph");
const ctx = canvas.getContext("2d");
const tooltip = document.getElementById("tooltip");
const wrap = document.getElementById("canvas-wrap");
let nodes = [], edges = [], focus = null, dragged = null, alpha = 1;

function resize() {
  canvas.width = wrap.clientWidth * devicePixelRatio;
  canvas.height = wrap.clientHeight * devicePixelRatio;
}
window.addEventListener("resize", resize);

async function json(url) { const r = await fetch(url); return r.json(); }

function buildGraph(graphEdges, watchlist) {
  const watch = new Set((watchlist || []).map(t => t.toUpperCase()));
  const degree = {};
  for (const e of graphEdges) {
    degree[e.source] = (degree[e.source] || 0) + 1;
    degree[e.target] = (degree[e.target] || 0) + 1;
  }
  const names = Object.keys(degree);
  const W = wrap.clientWidth, H = wrap.clientHeight;
  nodes = names.map((name, i) => {
    const angle = (2 * Math.PI * i) / names.length;
    const radius = Math.min(W, H) * 0.33;
    return {
      id: name, degree: degree[name], watch: watch.has(name),
      x: W / 2 + radius * Math.cos(angle), y: H / 2 + radius * Math.sin(angle),
      vx: 0, vy: 0,
    };
  });
  const byId = Object.fromEntries(nodes.map(n => [n.id, n]));
  edges = graphEdges
    .map(e => ({ ...e, a: byId[e.source], b: byId[e.target] }))
    .filter(e => e.a && e.b);
  document.getElementById("edge-count").textContent = edges.length + " edges · " + nodes.length + " tickers";
  alpha = 1;
}

function step() {
  for (const n of nodes) {
    n.vx *= 0.85; n.vy *= 0.85;
    for (const m of nodes) {
      if (m === n) continue;
      const dx = n.x - m.x, dy = n.y - m.y;
      const d2 = dx * dx + dy * dy || 1;
      const repulse = 2600 / d2;
      n.vx += (dx / Math.sqrt(d2)) * repulse * alpha;
      n.vy += (dy / Math.sqrt(d2)) * repulse * alpha;
    }
    const W = wrap.clientWidth, H = wrap.clientHeight;
    n.vx += (W / 2 - n.x) * 0.002 * alpha;
    n.vy += (H / 2 - n.y) * 0.002 * alpha;
  }
  for (const e of edges) {
    const dx = e.b.x - e.a.x, dy = e.b.y - e.a.y;
    const dist = Math.sqrt(dx * dx + dy * dy) || 1;
    const target = 150 - 60 * e.strength;
    const force = (dist - target) * 0.004 * alpha;
    e.a.vx += (dx / dist) * force; e.a.vy += (dy / dist) * force;
    e.b.vx -= (dx / dist) * force; e.b.vy -= (dy / dist) * force;
  }
  for (const n of nodes) {
    if (n === dragged) continue;
    n.x += n.vx; n.y += n.vy;
  }
  alpha *= 0.995;
}

function radiusOf(n) {
  const base = 8 + Math.min(14, n.degree * 1.6);
  return n.watch ? base + 5 : base;
}

function draw() {
  const W = wrap.clientWidth, H = wrap.clientHeight;
  ctx.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0);
  ctx.clearRect(0, 0, W, H);
  for (const e of edges) {
    if (focus && e.a.id !== focus && e.b.id !== focus) continue;
    ctx.strokeStyle = EDGE_COLORS[e.type] || "#8b949e";
    ctx.globalAlpha = focus ? 0.9 : 0.25 + 0.55 * e.strength;
    ctx.lineWidth = 1 + 3 * e.strength;
    ctx.beginPath();
    ctx.moveTo(e.a.x, e.a.y);
    ctx.lineTo(e.b.x, e.b.y);
    ctx.stroke();
    ctx.globalAlpha = 1;
  }
  for (const n of nodes) {
    if (focus && n.id !== focus) continue;
    const r = radiusOf(n);
    ctx.beginPath();
    ctx.arc(n.x, n.y, r, 0, 2 * Math.PI);
    ctx.fillStyle = n.watch ? "#1f6feb" : "#21262d";
    ctx.fill();
    ctx.lineWidth = n.id === focus ? 3 : 1.5;
    ctx.strokeStyle = n.watch ? "#79c0ff" : "#58a6ff";
    ctx.stroke();
    ctx.fillStyle = "#e6edf3";
    ctx.font = "600 12px -apple-system, sans-serif";
    ctx.textAlign = "center";
    ctx.fillText(n.id, n.x, n.y - r - 6);
  }
}

function loop() { step(); draw(); requestAnimationFrame(loop); }

function nodeAt(x, y) {
  for (const n of nodes) {
    const dx = x - n.x, dy = y - n.y;
    if (dx * dx + dy * dy <= radiusOf(n) * radiusOf(n) * 1.4) return n;
  }
  return null;
}

function edgeAt(x, y) {
  for (const e of edges) {
    const dx = e.b.x - e.a.x, dy = e.b.y - e.a.y;
    const len2 = dx * dx + dy * dy || 1;
    let t = ((x - e.a.x) * dx + (y - e.a.y) * dy) / len2;
    t = Math.max(0, Math.min(1, t));
    const px = e.a.x + t * dx, py = e.a.y + t * dy;
    const ex = x - px, ey = y - py;
    if (ex * ex + ey * ey < 36) return e;
  }
  return null;
}

function pos(ev) {
  const rect = canvas.getBoundingClientRect();
  return { x: ev.clientX - rect.left, y: ev.clientY - rect.top };
}

canvas.addEventListener("mousedown", ev => { const n = nodeAt(pos(ev).x, pos(ev).y); if (n) { dragged = n; alpha = Math.max(alpha, 0.5); } });
canvas.addEventListener("mousemove", ev => {
  const p = pos(ev);
  if (dragged) { dragged.x = p.x; dragged.y = p.y; return; }
  const n = nodeAt(p.x, p.y);
  const e = n ? null : edgeAt(p.x, p.y);
  if (n) {
    tooltip.style.display = "block";
    tooltip.style.left = (p.x + 14) + "px";
    tooltip.style.top = (p.y + 14) + "px";
    tooltip.innerHTML = "<b>" + n.id + "</b>" + (n.watch ? " · watchlist" : "") + "<br>" + n.degree + " relationships";
  } else if (e) {
    tooltip.style.display = "block";
    tooltip.style.left = (p.x + 14) + "px";
    tooltip.style.top = (p.y + 14) + "px";
    tooltip.innerHTML = "<b>" + EDGE_LABELS[e.type] + "</b><br>" + e.source + " ↔ " + e.target + "<br>strength " + e.strength.toFixed(2);
  } else { tooltip.style.display = "none"; }
});
window.addEventListener("mouseup", () => { dragged = null; });
canvas.addEventListener("click", ev => {
  const n = nodeAt(pos(ev).x, pos(ev).y);
  focus = (n && n.id !== focus) ? n.id : null;
});
canvas.addEventListener("dblclick", () => { focus = null; });

function legend() {
  const el = document.getElementById("legend");
  el.innerHTML = Object.keys(EDGE_COLORS).map(k =>
    '<div class="row"><span class="swatch" style="background:' + EDGE_COLORS[k] + '"></span>' + EDGE_LABELS[k] + "</div>"
  ).join("") + '<div class="row"><span class="node" style="background:#1f6feb"></span>watchlist ticker</div>';
}

function renderQueue(items) {
  const el = document.getElementById("queue");
  if (!items.length) { el.innerHTML = '<span class="muted">queue empty — run a cycle</span>'; return; }
  el.innerHTML = items.slice(0, 8).map(t =>
    '<div class="queue-item"><div class="head"><span>' +
    '<span class="ticker-chip">' + t.ticker + "</span>" +
    '<span class="tag ' + t.classification + '">' + t.classification + "</span></span>" +
    '<span class="score">' + t.score.toFixed(3) + "</span></div>" +
    '<div class="muted">' + t.headline + "</div></div>"
  ).join("");
}

(async function init() {
  resize(); legend(); loop();
  const health = await json("/health");
  const el = document.getElementById("health");
  el.textContent = "data " + (health.data_source ? "ok" : "down") + " · llm " + (health.llm ? "ok" : "heuristic") + " · " + (health.tickers || []).length + " tickers";
  el.classList.add("ok");
  document.getElementById("watchlist").textContent = (health.tickers || []).join(", ") || "—";
  const graph = await json("/graph");
  buildGraph(graph.edges, health.tickers);
  const queue = await json("/queue");
  renderQueue(queue.queue);
})();
</script>
</body>
</html>
"""

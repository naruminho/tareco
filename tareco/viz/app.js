(function () {
  "use strict";

  const DATA = window.__TARECO__;
  const cfg = DATA.config;
  const is3D = cfg.dim === 3;
  const REL = 4;
  const LABEL_TOP = 24;
  const FONT = 'ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif';
  const root = document.documentElement;
  const $ = (id) => document.getElementById(id);
  const T = tarecoText(cfg.lang);
  const insights = cfg.insights || [];
  const ICON = {
    chevron: '<svg class="icon sep" viewBox="0 0 24 24"><path d="m9 6 6 6-6 6"/></svg>',
    arrow: '<svg class="icon" viewBox="0 0 24 24"><path d="M5 12h14M13 6l6 6-6 6"/></svg>',
    line: '<svg class="icon" viewBox="0 0 24 24"><path d="M5 12h14"/></svg>',
  };

  // ------------------------------------------------------------------ theme

  let theme = cfg.theme;
  if (theme !== "dark" && theme !== "light") {
    let saved = null;
    try { saved = localStorage.getItem("tareco-theme"); } catch (e) { /* sandboxed */ }
    theme = saved || (matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark");
  }
  let C = {};
  function applyTheme() {
    root.dataset.theme = theme;
    const css = getComputedStyle(root);
    for (const k of ["bg", "text", "muted", "edge", "edge-faint", "ring", "accent"]) {
      C[k] = css.getPropertyValue("--" + k).trim();
    }
  }
  applyTheme();
  if (is3D) document.body.classList.add("is-3d");

  // ------------------------------------------------------------------- data

  const nodes = DATA.nodes;
  const links = DATA.links;
  const byId = new Map(nodes.map((n) => [n.id, n]));
  for (const n of nodes) {
    n.nbrs = new Set();
    n.out = [];
    n.links = [];
    n.faded = fade(n.color, is3D ? 0.12 : 0.14);
    n.key = norm(n.label);
  }
  for (const l of links) {
    const a = byId.get(l.source), b = byId.get(l.target);
    a.nbrs.add(b); b.nbrs.add(a);
    a.links.push(l);
    if (a !== b) b.links.push(l);
    a.out.push([b, l]);
    if (!cfg.directed && a !== b) b.out.push([a, l]);
  }
  [...nodes].sort((a, b) => b.val - a.val).forEach((n, i) => { n.rank = i; });

  function ends(l) {
    const a = typeof l.source === "object" ? l.source : byId.get(l.source);
    const b = typeof l.target === "object" ? l.target : byId.get(l.target);
    return [a, b];
  }
  function norm(s) {
    return String(s).toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
  }
  function esc(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }
  function fade(color, alpha) {
    if (color.startsWith("#")) {
      const h = color.slice(1);
      const v = h.length === 3 ? h.split("").map((c) => c + c).join("") : h;
      const r = parseInt(v.slice(0, 2), 16), g = parseInt(v.slice(2, 4), 16), b = parseInt(v.slice(4, 6), 16);
      return `rgba(${r},${g},${b},${alpha})`;
    }
    if (color.startsWith("hsl(")) return color.replace("hsl(", "hsla(").replace(")", `, ${alpha})`);
    return color;
  }
  function fmt(v) {
    if (typeof v === "number") {
      if (Number.isInteger(v)) return v.toLocaleString(T.locale);
      if (v !== 0 && Math.abs(v) < 0.001) return v.toExponential(2);
      return Number(v.toPrecision(4)).toLocaleString(T.locale, { maximumFractionDigits: 6 });
    }
    if (v === null || v === undefined) return "";
    if (typeof v === "object") return JSON.stringify(v);
    return String(v);
  }

  // ------------------------------------------------------------------ state

  const state = {
    hover: null,
    selected: null,
    pathMode: false,
    pathStart: null,
    path: null,
    hidden: new Set(),
    labels: true,
    frozen: false,
    spot: null,
  };
  let focus = null;

  function computeFocus() {
    if (state.path) return state.path;
    if (state.spot) return state.spot;
    const n = state.hover || state.selected;
    if (!n) return null;
    return { nodes: new Set([n, ...n.nbrs]), links: new Set(n.links), center: n };
  }
  function update() {
    focus = computeFocus();
    if (is3D) fg.nodeColor(fg.nodeColor()).linkColor(fg.linkColor()).linkWidth(fg.linkWidth());
  }
  function visible(n) {
    return !state.hidden.has(n.group);
  }

  // ------------------------------------------------------------------ graph

  const elem = $("graph");
  const fg = (is3D ? ForceGraph3D({ controlType: "orbit" }) : ForceGraph())(elem)
    .graphData({ nodes, links })
    .nodeId("id")
    .nodeVal((n) => n.val)
    .nodeRelSize(REL)
    .nodeLabel(nodeTip)
    .linkLabel(linkTip)
    .nodeVisibility(visible)
    .linkVisibility((l) => { const [a, b] = ends(l); return visible(a) && visible(b); })
    .linkCurvature((l) => l.curve)
    .linkColor(linkColor)
    .linkWidth(linkWidth)
    .backgroundColor(C.bg)
    .width(innerWidth)
    .height(innerHeight)
    .onNodeHover((n) => { state.hover = n || null; elem.style.cursor = n ? "pointer" : ""; update(); })
    .onNodeClick(onNodeClick)
    .onNodeRightClick((n) => setPinned(n, false))
    .onNodeDragEnd((n) => setPinned(n, true))
    .onBackgroundClick(clearAll)
    .cooldownTime(20000);

  if (cfg.directed) {
    fg.linkDirectionalArrowLength((l) => (is3D ? 3 : 3.5) + l.w)
      .linkDirectionalArrowRelPos(1)
      .linkDirectionalArrowColor(linkColor);
  }
  if (cfg.particles) {
    fg.linkDirectionalParticles(2)
      .linkDirectionalParticleWidth((l) => Math.max(1.6, l.w * 1.3))
      .linkDirectionalParticleSpeed((l) => 0.003 + 0.002 * l.w)
      .linkDirectionalParticleColor((l) => ends(l)[0].color);
  }

  const big = nodes.length > 800;
  fg.d3Force("charge").strength((n) => -(big ? 18 : 36) - 5 * n.val).distanceMax(big ? 260 : 520);
  fg.d3Force("link").distance((l) => {
    const [a, b] = ends(l);
    return 18 + (Math.sqrt(a.val) + Math.sqrt(b.val)) * REL;
  });

  if (is3D) {
    fg.showNavInfo(false)
      .nodeColor((n) => (focus && !focus.nodes.has(n) ? n.faded : n.color))
      .nodeOpacity(0.95)
      .nodeResolution(16)
      .linkOpacity(0.5);
  } else {
    fg.autoPauseRedraw(false)
      .nodeCanvasObjectMode(() => "replace")
      .nodeCanvasObject(drawNode)
      .nodePointerAreaPaint((n, color, ctx) => {
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.arc(n.x, n.y, Math.sqrt(n.val) * REL + 2, 0, 2 * Math.PI);
        ctx.fill();
      });
  }

  let fitted = false;
  setTimeout(() => { if (!fitted) fitNodes(nodes.filter(visible), 400); }, 900);
  fg.onEngineStop(() => { if (!fitted) { fitted = true; fitNodes(nodes.filter(visible), 500); } });
  addEventListener("resize", () => fg.width(innerWidth).height(innerHeight));

  function linkColor(l) {
    if (!focus) return C.edge;
    if (!focus.links.has(l)) return C["edge-faint"];
    if (state.path || !focus.center) return C.accent;
    return fade(focus.center.color, 0.85);
  }
  function linkWidth(l) {
    const hot = focus && focus.links.has(l);
    if (is3D) return hot ? 1.2 : 0;
    return hot ? l.w * 1.6 + 0.8 : l.w;
  }

  function drawNode(n, ctx, scale) {
    const r = Math.sqrt(n.val) * REL;
    const dim = focus && !focus.nodes.has(n);
    ctx.beginPath();
    ctx.arc(n.x, n.y, r, 0, 2 * Math.PI);
    ctx.fillStyle = dim ? n.faded : n.color;
    ctx.fill();
    const marked = n === state.selected || n === state.pathStart || (state.path && state.path.ends.has(n));
    ctx.lineWidth = (marked ? 2.5 : 1) / scale;
    ctx.strokeStyle = marked ? C.ring : dim ? "transparent" : C.bg;
    ctx.stroke();
    if (n.pinned) {
      ctx.beginPath();
      ctx.arc(n.x + r * 0.72, n.y - r * 0.72, Math.max(1.6 / scale, r * 0.26), 0, 2 * Math.PI);
      ctx.fillStyle = C.text;
      ctx.fill();
    }
    let showLabel;
    if (focus) showLabel = !dim && (focus === state.path || focus.center === n || focus.nodes.size <= 40 || r * scale > 6);
    else showLabel = state.labels && (n.rank < LABEL_TOP || r * scale > 9);
    if (!showLabel) return;
    const size = 12 / scale;
    ctx.font = `${focus && focus.center === n ? 650 : 500} ${size}px ${FONT}`;
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    const y = n.y + r + 3 / scale;
    ctx.lineJoin = "round";
    ctx.lineWidth = 3 / scale;
    ctx.strokeStyle = C.bg;
    ctx.strokeText(n.label, n.x, y);
    ctx.fillStyle = C.text;
    ctx.fillText(n.label, n.x, y);
  }

  function nodeTip(n) {
    const g = DATA.config.legend;
    let sub = "";
    if (g && g.kind === "category" && n.group !== null) sub = `${esc(g.title || "group")} ${esc(n.group || "none")}`;
    else if (g && g.kind === "scale" && g.title && n.metrics[g.title] !== undefined) sub = `${esc(g.title)} ${fmt(n.metrics[g.title])}`;
    else if (g && g.kind === "scale" && g.title && n.attrs[g.title] !== undefined) sub = `${esc(g.title)} ${fmt(n.attrs[g.title])}`;
    return `<div class="tip"><b>${esc(n.label)}</b>${sub ? `<div class="sub">${sub}</div>` : ""}</div>`;
  }
  function linkTip(l) {
    const [a, b] = ends(l);
    const rows = Object.entries(l.attrs).map(([k, v]) => `<div class="sub">${esc(k)} ${esc(fmt(v))}</div>`).join("");
    return `<div class="tip"><span class="edge"><b>${esc(a.label)}</b>${cfg.directed ? ICON.arrow : ICON.line}<b>${esc(b.label)}</b></span>${rows}</div>`;
  }

  // ------------------------------------------------------------ interaction

  function onNodeClick(n) {
    if (state.pathMode) return pathClick(n);
    select(n);
  }
  function select(n) {
    state.selected = n;
    state.spot = null;
    state.path = null;
    state.pathStart = null;
    showNodePanel(n);
    update();
    flyTo(n);
  }
  function clearAll() {
    state.selected = null;
    state.spot = null;
    state.path = null;
    state.pathStart = null;
    $("panel").hidden = true;
    update();
  }
  function flyTo(n) {
    if (is3D) {
      const d = 260;
      const len = Math.hypot(n.x, n.y, n.z) || 1;
      const k = 1 + d / len;
      fg.cameraPosition({ x: n.x * k, y: n.y * k, z: n.z * k }, n, 900);
    } else {
      const k = fg.zoom() < 1.6 ? 2.2 : fg.zoom();
      const [left, right] = margins();
      fg.centerAt(n.x + (right - left) / 2 / k, n.y, 600);
      if (k !== fg.zoom()) fg.zoom(k, 600);
    }
  }
  // screen space taken by the floating cards on each side (wide screens only)
  function margins() {
    if (innerWidth <= 720) return [0, 0];
    const panel = $("panel");
    return [document.querySelector(".header").offsetWidth + 16, panel.hidden ? 0 : panel.offsetWidth + 16];
  }

  // zoom to a set of nodes, leaving room for the floating cards
  function fitNodes(list, ms = 700) {
    if (!list.length) return;
    if (is3D) { const s = new Set(list); fg.zoomToFit(ms, 80, (n) => s.has(n)); return; }
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    for (const n of list) {
      const r = Math.sqrt(n.val) * REL;
      x0 = Math.min(x0, n.x - r); x1 = Math.max(x1, n.x + r);
      y0 = Math.min(y0, n.y - r); y1 = Math.max(y1, n.y + r + 14);
    }
    const [left, right] = margins();
    const w = Math.max(80, innerWidth - left - right - 80), h = Math.max(80, innerHeight - 100);
    const k = Math.min(3, w / Math.max(1, x1 - x0), h / Math.max(1, y1 - y0));
    fg.centerAt((x0 + x1) / 2 + (right - left) / 2 / k, (y0 + y1) / 2, ms);
    fg.zoom(k, ms);
  }
  function setPinned(n, on) {
    n.pinned = on;
    if (on) { n.fx = n.x; n.fy = n.y; if (is3D) n.fz = n.z; }
    else if (!state.frozen) { n.fx = n.fy = n.fz = undefined; fg.d3ReheatSimulation(); }
    if (state.selected === n) $("btn-pin").classList.toggle("on", on);
  }

  // shortest path, respecting direction and hidden groups
  function pathClick(n) {
    if (!state.pathStart || state.path) {
      state.pathStart = n;
      state.path = null;
      state.selected = null;
      $("panel").hidden = true;
      update();
      return;
    }
    if (n === state.pathStart) return;
    const p = findPath(state.pathStart, n);
    if (!p) {
      toast(T.noPath(state.pathStart.label, n.label));
      return;
    }
    state.path = p;
    showPathPanel(p);
    update();
    fitNodes(p.list);
  }
  function findPath(a, b) {
    const prev = new Map([[a, null]]);
    const queue = [a];
    for (let i = 0; i < queue.length && !prev.has(b); i++) {
      const u = queue[i];
      for (const [v, l] of u.out) {
        if (!prev.has(v) && visible(v)) { prev.set(v, [u, l]); queue.push(v); }
      }
    }
    if (!prev.has(b)) return null;
    const list = [b], ls = new Set();
    for (let cur = b; prev.get(cur); ) {
      const [u, l] = prev.get(cur);
      ls.add(l); list.push(u); cur = u;
    }
    list.reverse();
    return { nodes: new Set(list), links: ls, list, ends: new Set([a, b]), center: null };
  }

  let toastTimer = null;
  function toast(text) {
    const t = $("toast");
    t.textContent = text;
    t.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { t.hidden = true; }, 2600);
  }

  // ----------------------------------------------------------------- panel

  function chip(n) {
    return `<button class="chip" data-id="${n.id}"><span class="dot" style="background:${n.color}"></span><span>${esc(n.label)}</span></button>`;
  }
  function kv(obj) {
    const rows = Object.entries(obj).filter(([, v]) => v !== null && v !== undefined && v !== "");
    if (!rows.length) return "";
    return `<dl class="kv">${rows.map(([k, v]) => `<dt title="${esc(k)}">${esc(k)}</dt><dd>${esc(fmt(v))}</dd>`).join("")}</dl>`;
  }
  function showNodePanel(n) {
    $("panel-dot").style.background = n.color;
    $("panel-dot").hidden = false;
    $("panel-title").textContent = n.label;
    $("btn-pin").hidden = false;
    $("btn-pin").classList.toggle("on", !!n.pinned);
    const nbrs = [...n.nbrs].filter((m) => m !== n).sort((a, b) => b.val - a.val);
    const shown = nbrs.slice(0, 80);
    let html = `<div class="section-title">${T.metrics}</div>${kv(n.metrics)}`;
    const attrs = kv(n.attrs);
    if (attrs) html += `<div class="section-title">${T.attributes}</div>${attrs}`;
    if (nbrs.length) {
      html += `<div class="section-title">${T.neighbors} <span class="muted">${fmt(nbrs.length)}</span></div><div class="chips">${shown.map(chip).join("")}`;
      if (nbrs.length > shown.length) html += `<span class="muted">+${nbrs.length - shown.length}</span>`;
      html += "</div>";
    }
    $("panel-body").innerHTML = html;
    $("panel").hidden = false;
  }
  function showPathPanel(p) {
    $("panel-dot").hidden = true;
    $("panel-title").textContent = `${p.list.length - 1} ${p.list.length === 2 ? T.step : T.steps}`;
    $("btn-pin").hidden = true;
    $("panel-body").innerHTML = `<div class="section-title">${T.pathTitle}</div><div class="chips">${p.list.map(chip).join(ICON.chevron)}</div>`;
    $("panel").hidden = false;
  }

  // plain-language findings; clicking one lights up the nodes it talks about
  const groupColor = (label) => {
    const it = cfg.legend && cfg.legend.kind === "category" && cfg.legend.metric === "community"
      ? cfg.legend.items.find((x) => x.label === label) : null;
    return it ? it.color : null;
  };
  function showInsights() {
    state.selected = null;
    state.path = null;
    $("panel-dot").hidden = true;
    $("panel-title").textContent = T.insights;
    $("btn-pin").hidden = true;
    $("panel-body").innerHTML = `<div class="findings">${tarecoInsightsHtml(insights, groupColor, esc)}</div>`;
    $("panel").hidden = false;
    update();
  }
  function spotlight(k) {
    const list = insights[k].nodes.map((i) => byId.get(i)).filter((n) => n && visible(n));
    if (!list.length) return;
    const set = new Set(list);
    const ls = new Set(links.filter((l) => { const [a, b] = ends(l); return set.has(a) && set.has(b); }));
    state.spot = { nodes: set, links: ls, center: null };
    for (const el of document.querySelectorAll(".finding")) el.classList.toggle("on", el.dataset.k === String(k));
    update();
    fitNodes(list);
  }
  $("panel-body").addEventListener("click", (e) => {
    const b = e.target.closest(".chip");
    if (b) return select(byId.get(Number(b.dataset.id)));
    const f = e.target.closest("button.finding");
    if (f) spotlight(Number(f.dataset.k));
  });
  $("btn-insights").hidden = insights.length === 0;
  $("btn-insights").onclick = showInsights;
  $("btn-close").onclick = clearAll;
  $("btn-pin").onclick = () => { if (state.selected) setPinned(state.selected, !state.selected.pinned); };

  // ---------------------------------------------------------------- toolbar

  $("btn-fit").onclick = () => fitNodes(nodes.filter(visible), 600);
  $("btn-labels").onclick = (e) => {
    state.labels = !state.labels;
    e.currentTarget.classList.toggle("on", state.labels);
  };
  $("btn-physics").onclick = (e) => {
    state.frozen = !state.frozen;
    e.currentTarget.classList.toggle("on", state.frozen);
    e.currentTarget.dataset.tip = state.frozen ? T.resume : T.freeze;
    for (const n of nodes) {
      if (n.pinned) continue;
      if (state.frozen) { n.fx = n.x; n.fy = n.y; if (is3D) n.fz = n.z; }
      else n.fx = n.fy = n.fz = undefined;
    }
    if (!state.frozen) fg.d3ReheatSimulation();
  };
  $("btn-path").onclick = (e) => {
    state.pathMode = !state.pathMode;
    e.currentTarget.classList.toggle("on", state.pathMode);
    state.pathStart = null;
    state.path = null;
    if (!state.pathMode && !state.selected) $("panel").hidden = true;
    update();
  };
  $("btn-theme").onclick = () => {
    theme = theme === "dark" ? "light" : "dark";
    try { localStorage.setItem("tareco-theme", theme); } catch (e) { /* sandboxed */ }
    applyTheme();
    fg.backgroundColor(C.bg);
    update();
  };
  $("btn-png").onclick = () => {
    const src = elem.querySelector("canvas");
    const out = document.createElement("canvas");
    out.width = src.width;
    out.height = src.height;
    const ctx = out.getContext("2d");
    ctx.fillStyle = C.bg;
    ctx.fillRect(0, 0, out.width, out.height);
    ctx.drawImage(src, 0, 0);
    const a = document.createElement("a");
    a.download = (cfg.title || "graph").replace(/[^\w\- ]+/g, "").trim().replace(/\s+/g, "-") + ".png";
    a.href = out.toDataURL("image/png");
    a.click();
  };

  // ----------------------------------------------------------------- header

  $("title").textContent = cfg.title || "";
  const counted = (shown, total, word) =>
    shown < total ? `${fmt(shown)} ${T.of} ${fmt(total)} ${word}` : `${fmt(total)} ${word}`;
  const total = cfg.total || cfg.counts;
  $("counts").textContent = `${counted(cfg.counts.nodes, total.nodes, T.nodes)} \u00b7 ${counted(cfg.counts.edges, total.edges, T.edges)}`;

  // ----------------------------------------------------------------- search

  const input = $("search"), results = $("results");
  let hits = [], active = 0;
  function renderResults() {
    results.hidden = hits.length === 0;
    results.innerHTML = hits.map((n, i) =>
      `<li data-id="${n.id}" class="${i === active ? "active" : ""}"><span class="dot" style="background:${n.color}"></span>${esc(n.label)}</li>`).join("");
  }
  input.addEventListener("input", () => {
    const q = norm(input.value.trim());
    active = 0;
    hits = !q ? [] : nodes.filter((n) => n.key.includes(q))
      .sort((a, b) => (b.key.startsWith(q) - a.key.startsWith(q)) || b.val - a.val)
      .slice(0, 8);
    renderResults();
  });
  input.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      if (!hits.length) return;
      active = (active + (e.key === "ArrowDown" ? 1 : hits.length - 1)) % hits.length;
      renderResults();
      e.preventDefault();
    } else if (e.key === "Enter" && hits.length) {
      pick(hits[active]);
    } else if (e.key === "Escape") {
      input.value = ""; hits = []; renderResults(); input.blur();
    }
  });
  results.addEventListener("mousedown", (e) => {
    const li = e.target.closest("li");
    if (li) { e.preventDefault(); pick(byId.get(Number(li.dataset.id))); }
  });
  input.addEventListener("blur", () => { results.hidden = true; });
  input.addEventListener("focus", () => { if (hits.length) results.hidden = false; });
  function pick(n) {
    if (!visible(n)) { state.hidden.delete(n.group); refreshVisibility(); }
    input.value = ""; hits = []; renderResults(); input.blur();
    if (state.pathMode) pathClick(n); else select(n);
  }
  addEventListener("keydown", (e) => {
    if (e.target === input) return;
    if (e.key === "/") { e.preventDefault(); input.focus(); }
    else if (e.key === "Escape") clearAll();
  });

  // ----------------------------------------------------------------- legend

  const legend = cfg.legend;
  const LEGEND_LIMIT = 12;
  let legendAll = false;
  function refreshVisibility() {
    fg.nodeVisibility(fg.nodeVisibility()).linkVisibility(fg.linkVisibility());
    if (state.selected && !visible(state.selected)) clearAll();
    if (state.path && [...state.path.nodes].some((n) => !visible(n))) clearAll();
    renderLegend();
  }
  function renderLegend() {
    const box = $("legend");
    let html = "";
    if (legend && legend.kind === "category") {
      const items = legendAll ? legend.items : legend.items.slice(0, LEGEND_LIMIT);
      html += legend.title ? `<div class="legend-title">${esc(legend.title)}</div>` : "";
      html += items.map((it) => {
        const key = it.missing ? "" : it.label;
        const name = it.missing ? `<span class="none">${T.none}</span>` : esc(it.label);
        const note = it.note ? `<span class="note">${esc(it.note)}</span>` : "";
        return `<button class="legend-item${state.hidden.has(key) ? " off" : ""}" data-key="${esc(key)}"><span class="dot" style="background:${it.color}"></span><span class="name">${name}${note}</span><span class="count">${fmt(it.count)}</span></button>`;
      }).join("");
      if (legend.items.length > LEGEND_LIMIT) {
        html += `<button class="legend-more" data-more="1">${legendAll ? T.less : T.more(legend.items.length - LEGEND_LIMIT)}</button>`;
      }
    } else if (legend && legend.kind === "scale") {
      html += legend.title ? `<div class="legend-title">${esc(legend.title)}</div>` : "";
      html += `<div class="scale-bar" style="background:linear-gradient(90deg,${legend.colors.join(",")})"></div>`;
      html += `<div class="scale-labels"><span>${fmt(legend.min)}</span><span>${fmt(legend.max)}</span></div>`;
    }
    if (cfg.size) {
      html += `<div class="legend-size"><svg viewBox="0 0 26 14"><circle cx="4" cy="9" r="2.5"/><circle cx="11.5" cy="8" r="4"/><circle cx="20.5" cy="7" r="5.5"/></svg>${esc(cfg.size)}</div>`;
    }
    box.innerHTML = html;
    box.hidden = !html;
  }
  $("legend").addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    if (b.dataset.more) { legendAll = !legendAll; renderLegend(); return; }
    const key = b.dataset.key;
    if (state.hidden.has(key)) state.hidden.delete(key); else state.hidden.add(key);
    refreshVisibility();
  });
  $("legend").addEventListener("dblclick", (e) => {
    const b = e.target.closest(".legend-item");
    if (!b) return;
    const key = b.dataset.key;
    const keys = legend.items.map((it) => (it.missing ? "" : it.label));
    const solo = keys.every((k) => (k === key) !== state.hidden.has(k));
    state.hidden = solo ? new Set() : new Set(keys.filter((k) => k !== key));
    refreshVisibility();
  });
  renderLegend();
})();

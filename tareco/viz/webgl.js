(function () {
  "use strict";

  const DATA = window.__TARECO__;
  const cfg = DATA.config;
  const N = DATA.nodes, E = DATA.edges, G = DATA.groups;
  const n = N.label.length;
  const m = E.e.length >> 1;
  const groupCount = G.label.length;
  const FONT = 'ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif';
  const root = document.documentElement;
  const container = document.getElementById("graph");
  const $ = (id) => document.getElementById(id);
  const T = tarecoText(cfg.lang);
  const insights = cfg.insights || [];
  const ICON = { chevron: '<svg class="icon sep" viewBox="0 0 24 24"><path d="m9 6 6 6-6 6"/></svg>' };

  document.body.classList.add("is-webgl");
  container.classList.add("webgl");

  // ------------------------------------------------------------------ theme

  let theme = cfg.theme;
  if (theme !== "dark" && theme !== "light") {
    let saved = null;
    try { saved = localStorage.getItem("tareco-theme"); } catch (e) { /* sandboxed */ }
    theme = saved || (matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark");
  }
  const C = {};
  function applyTheme() {
    root.dataset.theme = theme;
    const css = getComputedStyle(root);
    for (const k of ["bg", "text", "muted", "edge", "edge-faint", "ring", "accent", "fade", "panel-solid"]) {
      C[k] = css.getPropertyValue("--" + k).trim();
    }
  }
  applyTheme();

  // ---------------------------------------------------------------- helpers

  function esc(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }
  function norm(s) {
    return String(s).toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
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
  const color = (i) => N.colors[N.c[i]];
  function withAlpha(css, alpha) {
    const m = css.match(/[\d.]+/g);
    return m && m.length >= 3 ? `rgba(${m[0]},${m[1]},${m[2]},${alpha.toFixed(3)})` : css;
  }
  // dense graphs need fainter edges, or the overlap turns into a white blob
  const edgeAlpha = (count) => Math.max(0.03, Math.min(0.3, 4 / Math.sqrt(Math.max(1, count))));
  const radius = new Float32Array(n);
  for (let i = 0; i < n; i++) radius[i] = 1.4 + Math.sqrt(N.size[i]) * 1.1;
  let edgeSize = null;
  if (E.w) edgeSize = E.w.map((w) => (w === null ? 0.6 : w * 0.6));

  // neighbors over everything embedded (CSR), for the panel and for jumping between views
  const nbStart = new Int32Array(n + 1);
  for (let e = 0; e < m; e++) { nbStart[E.e[2 * e] + 1]++; nbStart[E.e[2 * e + 1] + 1]++; }
  for (let i = 0; i < n; i++) nbStart[i + 1] += nbStart[i];
  const nbList = new Int32Array(2 * m);
  {
    const fill = nbStart.slice(0, n);
    for (let e = 0; e < m; e++) {
      const s = E.e[2 * e], t = E.e[2 * e + 1];
      nbList[fill[s]++] = t;
      nbList[fill[t]++] = s;
    }
  }
  const X = Float32Array.from(N.x), Y = Float32Array.from(N.y);
  let searchKeys = null;

  // ------------------------------------------------------------------ state

  const state = {
    view: null,
    hover: null,
    selected: null,
    pathMode: false,
    pathStart: null,
    path: null,
    hidden: new Set(),
    spot: null,
    labels: true,
  };
  let graph = null, renderer = null, layout = null, focus = null;
  let viewIdx = null;      // local position -> global node index (node views)
  let inView = null;       // Uint8Array: is global node i in the current view
  let localOf = null;      // node key -> position in the layout arrays
  let renderMs = 16, renderStart = 0, lastApply = 0, applyTimer = 0;
  let edgeColor = "";
  let generation = 0, pendingFrame = null, frameScheduled = false;

  // ------------------------------------------------------------------ views

  function buildView(view) {
    if (layout) layout.stop();
    if (renderer) renderer.kill();
    state.view = view;
    drag.node = null;
    drag.moved = false;
    generation++;
    pendingFrame = null;
    frameScheduled = false;
    clearTimeout(applyTimer);
    localOf = new Map();
    state.hover = state.selected = state.pathStart = state.path = state.spot = null;
    focus = null;
    $("panel").hidden = true;

    const overview = view.kind === "overview";
    graph = new graphology.Graph({ type: overview || !cfg.directed ? "undirected" : "directed", multi: false, allowSelfLoops: false });
    let lx, ly, lr, ledges, lstrength = null;
    if (overview) {
      const biggest = Math.max(...G.size);
      lx = []; ly = []; lr = [];
      for (let gi = 0; gi < groupCount; gi++) {
        const r = 4 + 22 * Math.sqrt(G.size[gi] / biggest);
        graph.addNode("g" + gi, { x: G.x[gi], y: G.y[gi], size: r, color: G.color[gi], label: G.label[gi], count: G.size[gi], note: G.note[gi], g: gi });
        localOf.set("g" + gi, gi);
        lx.push(G.x[gi]); ly.push(G.y[gi]); lr.push(r * 2.5);
      }
      const ge = G.e.length >> 1;
      const wmax = Math.max(1, ...G.w);
      ledges = [];
      lstrength = [];
      for (let k = 0; k < ge; k++) {
        const a = G.e[2 * k], b = G.e[2 * k + 1];
        // strong links between groups stand out, weak ones nearly vanish
        const share = G.w[k] / wmax;
        graph.addEdge("g" + a, "g" + b, { size: 0.5 + 6 * share, color: withAlpha(C.edge, 0.03 + 0.6 * share), w: G.w[k] });
        ledges.push(a, b);
        lstrength.push(0.05 + share);
      }
      viewIdx = null;
      inView = null;
    } else {
      inView = new Uint8Array(n);
      viewIdx = [];
      for (let i = 0; i < n; i++) {
        if (view.kind === "all" || N.grp[i] === view.g) { inView[i] = 1; viewIdx.push(i); }
      }
      const local = new Int32Array(n).fill(-1);
      lx = []; ly = []; lr = [];
      viewIdx.forEach((i, k) => {
        local[i] = k;
        graph.addNode(String(i), { x: X[i], y: Y[i], size: radius[i], color: color(i), label: N.label[i], i });
        localOf.set(String(i), k);
        lx.push(X[i]); ly.push(Y[i]); lr.push(radius[i]);
      });
      ledges = [];
      for (let e = 0; e < m; e++) if (inView[E.e[2 * e]] && inView[E.e[2 * e + 1]]) ledges.push(e);
      edgeColor = withAlpha(C.edge, edgeAlpha(ledges.length));
      const pairs = [];
      for (const e of ledges) {
        const s = E.e[2 * e], t = E.e[2 * e + 1];
        graph.addEdgeWithKey("e" + e, String(s), String(t), { size: edgeSize ? edgeSize[e] : 0.6, color: edgeColor });
        pairs.push(local[s], local[t]);
      }
      ledges = pairs;
    }

    const big = graph.size > 100000;
    renderer = new Sigma(graph, container, {
      allowInvalidContainer: true,
      renderLabels: state.labels,
      labelFont: FONT,
      labelSize: 12,
      labelWeight: "500",
      labelColor: { color: C.text },
      labelRenderedSizeThreshold: overview ? 0 : 7,
      labelDensity: overview ? 1 : 0.6,
      labelGridCellSize: overview ? 60 : 90,
      defaultEdgeType: cfg.directed && !overview ? "arrow" : "line",
      zIndex: true,
      hideEdgesOnMove: big,
      minCameraRatio: 0.005,
      maxCameraRatio: 20,
      stagePadding: 40,
      nodeReducer,
      edgeReducer,
      defaultDrawNodeHover: drawHover,
    });
    bindEvents();
    renderer.on("beforeRender", () => { renderStart = performance.now(); });
    renderer.on("afterRender", () => { renderMs = renderMs * 0.7 + (performance.now() - renderStart) * 0.3; });
    renderCrumb();
    renderCounts();
    renderLegend();
    $("btn-groups").classList.toggle("on", overview);
    $("btn-path").disabled = overview;
    if (overview && state.pathMode) setPathMode(false);

    const nodesInView = lx.length;
    const gen = generation;
    layout = tarecoRunLayout({
      n: nodesInView,
      x: Float64Array.from(lx),
      y: Float64Array.from(ly),
      radius: Float64Array.from(lr),
      edges: Int32Array.from(ledges),
      edgeStrength: lstrength && Float64Array.from(lstrength),
      linkDistance: overview ? 40 : 12,
      charge: overview ? 60 : 24,
      chargePerArea: overview ? 2 : 2.5,
      gravity: overview ? 0.08 : 0.02,
      alpha: overview ? 1 : nodesInView > 5000 ? 0.6 : 1,
      ticks: nodesInView > 20000 ? 200 : 300,
      group: overview || view.kind !== "all" ? null : Int32Array.from(viewIdx, (i) => N.grp[i]),
      groupPull: 0.02,
    }, (x, y, done) => { if (gen === generation) onLayoutFrame(x, y, done); });
    setPhysicsButton(true);
  }

  // Positions arrive faster than a big graph can be drawn; apply them no more often
  // than rendering allows, so the page keeps answering the mouse while it settles.
  function onLayoutFrame(x, y, done) {
    pendingFrame = [x, y];
    if (done) setPhysicsButton(false);
    if (frameScheduled) return;
    frameScheduled = true;
    const wait = Math.max(0, lastApply + renderMs * 1.5 - performance.now());
    applyTimer = setTimeout(() => requestAnimationFrame(applyFrame), done ? 0 : wait);
  }
  function applyFrame() {
    frameScheduled = false;
    lastApply = performance.now();
    if (!pendingFrame || !graph) return;
    const [px, py] = pendingFrame;
    pendingFrame = null;
    let k = 0;
    const dragged = drag.node;
    graph.updateEachNodeAttributes((key, attr) => {
      if (key !== dragged) { attr.x = px[k]; attr.y = py[k]; }
      if (viewIdx) { X[viewIdx[k]] = attr.x; Y[viewIdx[k]] = attr.y; }
      k++;
      return attr;
    }, { attributes: ["x", "y"] });
  }

  // -------------------------------------------------------------- reducers

  function hiddenNode(data) {
    return state.hidden.size > 0 && data.i !== undefined && state.hidden.has(N.cat[data.i]);
  }
  function nodeReducer(key, data) {
    if (hiddenNode(data)) return { ...data, hidden: true };
    if (focus) {
      if (focus.nodes.has(key)) {
        return { ...data, zIndex: 2, forceLabel: key === focus.center || focus.nodes.size <= 50, highlighted: key === state.selected };
      }
      return { ...data, color: C.fade, label: "", zIndex: 0 };
    }
    if (key === state.selected) return { ...data, highlighted: true, zIndex: 2 };
    return data;
  }
  function edgeReducer(key, data) {
    if (focus) {
      if (focus.edges.has(key)) return { ...data, color: focus.color, size: Math.max(1.4, data.size * 1.8), zIndex: 1 };
      return { ...data, hidden: true };
    }
    return data;
  }
  function computeFocus() {
    if (state.path) return state.path;
    if (state.spot) return state.spot;
    const key = state.hover || state.selected;
    if (!key || !graph.hasNode(key)) return null;
    return {
      nodes: new Set([key, ...graph.neighbors(key)]),
      edges: new Set(graph.edges(key)),
      center: key,
      color: graph.getNodeAttribute(key, "color"),
    };
  }
  function update() {
    focus = computeFocus();
    renderer.refresh({ skipIndexation: true });
  }

  function drawHover(ctx, data, settings) {
    const size = settings.labelSize;
    const known = graph && graph.hasNode(data.key);
    const count = known ? graph.getNodeAttribute(data.key, "count") : undefined;
    const note = known ? graph.getNodeAttribute(data.key, "note") : undefined;
    const label = (data.label || "") + (count !== undefined ? `  ${fmt(count)}` : "") + (note ? ` \u00b7 ${note}` : "");
    ctx.beginPath();
    ctx.arc(data.x, data.y, data.size + 2.5, 0, Math.PI * 2);
    ctx.lineWidth = 2;
    ctx.strokeStyle = C.ring;
    ctx.stroke();
    if (!label) return;
    ctx.font = `600 ${size}px ${FONT}`;
    const w = ctx.measureText(label).width;
    const h = size + 10, x0 = data.x + data.size + 7, y0 = data.y - h / 2;
    ctx.save();
    ctx.shadowColor = "rgba(0,0,0,0.3)";
    ctx.shadowBlur = 10;
    ctx.fillStyle = C["panel-solid"];
    ctx.beginPath();
    if (ctx.roundRect) ctx.roundRect(x0, y0, w + 16, h, 7); else ctx.rect(x0, y0, w + 16, h);
    ctx.fill();
    ctx.restore();
    ctx.fillStyle = C.text;
    ctx.textBaseline = "middle";
    ctx.fillText(label, x0 + 8, data.y + 0.5);
  }

  // ---------------------------------------------------------------- events

  const drag = { node: null, moved: false };
  function bindEvents() {
    renderer.on("enterNode", ({ node }) => {
      state.hover = node;
      container.style.cursor = "pointer";
      update();
    });
    renderer.on("leaveNode", () => {
      state.hover = null;
      container.style.cursor = "";
      update();
    });
    renderer.on("clickNode", ({ node }) => {
      if (drag.moved) return;
      if (state.view.kind === "overview") return openGroup(graph.getNodeAttribute(node, "g"));
      if (state.pathMode) return pathClick(node);
      select(node);
    });
    renderer.on("clickStage", () => { if (!drag.moved) clearAll(); });
    renderer.on("rightClickNode", ({ node, event }) => {
      if (event && event.preventSigmaDefault) event.preventSigmaDefault();
      setPinned(node, false);
    });
    renderer.on("downNode", ({ node }) => {
      drag.node = node;
      drag.moved = false;
      if (!renderer.getCustomBBox()) renderer.setCustomBBox(renderer.getBBox());
    });
    renderer.on("moveBody", ({ event }) => {
      if (!drag.node) return;
      drag.moved = true;
      const pos = renderer.viewportToGraph(event);
      graph.setNodeAttribute(drag.node, "x", pos.x);
      graph.setNodeAttribute(drag.node, "y", pos.y);
      layout.pin(localIndex(drag.node), pos.x, pos.y);
      event.preventSigmaDefault();
      event.original.preventDefault();
      event.original.stopPropagation();
    });
    const release = () => {
      if (drag.node && drag.moved) setPinned(drag.node, true);
      drag.node = null;
      setTimeout(() => { drag.moved = false; }, 0);
    };
    renderer.on("upNode", release);
    renderer.on("upStage", release);
  }

  function localIndex(key) {
    return localOf.get(key);
  }
  function setPinned(key, on) {
    graph.setNodeAttribute(key, "pinned", on);
    const k = localIndex(key);
    if (on) layout.pin(k, graph.getNodeAttribute(key, "x"), graph.getNodeAttribute(key, "y"));
    else { layout.unpin(k); if (!layout.running) { layout.resume(0.1); setPhysicsButton(true); } }
    if (state.selected === key) $("btn-pin").classList.toggle("on", on);
  }

  function select(key) {
    state.selected = key;
    state.spot = null;
    state.path = null;
    state.pathStart = null;
    showNodePanel(key);
    update();
    flyTo(key);
  }
  function clearAll() {
    state.selected = null;
    state.spot = null;
    state.path = null;
    state.pathStart = null;
    $("panel").hidden = true;
    update();
  }
  function flyTo(key) {
    const d = renderer.getNodeDisplayData(key);
    if (!d) return;
    const camera = renderer.getCamera();
    camera.animate({ x: d.x, y: d.y, ratio: Math.min(camera.ratio, 0.35) }, { duration: 500 });
  }

  // jump to a node that may live in another view
  function reveal(i) {
    if (state.hidden.has(N.cat[i])) { state.hidden.delete(N.cat[i]); renderLegend(); }
    if (!inView || !inView[i]) buildView(state.view.kind === "group" ? { kind: "group", g: N.grp[i] } : { kind: "all" });
    return String(i);
  }

  function openGroup(gi) {
    buildView({ kind: "group", g: gi });
  }

  // ------------------------------------------------------------------ path

  function setPathMode(on) {
    state.pathMode = on;
    $("btn-path").classList.toggle("on", on);
    state.pathStart = null;
    state.path = null;
    if (!on && !state.selected) $("panel").hidden = true;
    if (renderer) update();
  }
  function pathClick(key) {
    if (!state.pathStart || state.path) {
      state.pathStart = key;
      state.path = null;
      state.selected = key;
      $("panel").hidden = true;
      update();
      return;
    }
    if (key === state.pathStart) return;
    const p = findPath(state.pathStart, key);
    if (!p) {
      toast(T.noPath(graph.getNodeAttribute(state.pathStart, "label"), graph.getNodeAttribute(key, "label")));
      return;
    }
    state.path = p;
    state.selected = null;
    showPathPanel(p);
    update();
    fitKeys(p.list);
  }
  function fitKeys(keys) {
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    for (const k of keys) {
      const d = renderer.getNodeDisplayData(k);
      if (!d) continue;
      x0 = Math.min(x0, d.x); x1 = Math.max(x1, d.x);
      y0 = Math.min(y0, d.y); y1 = Math.max(y1, d.y);
    }
    if (x0 === Infinity) return;
    const ratio = Math.min(1.2, Math.max(0.04, Math.max(x1 - x0, y1 - y0) * 1.5));
    renderer.getCamera().animate({ x: (x0 + x1) / 2, y: (y0 + y1) / 2, ratio }, { duration: 600 });
  }
  function findPath(a, b) {
    const prev = new Map([[a, null]]);
    const queue = [a];
    const next = cfg.directed ? (k) => graph.outNeighbors(k) : (k) => graph.neighbors(k);
    for (let h = 0; h < queue.length && !prev.has(b); h++) {
      const u = queue[h];
      for (const v of next(u)) {
        if (!prev.has(v) && !hiddenNode(graph.getNodeAttributes(v))) { prev.set(v, u); queue.push(v); }
      }
    }
    if (!prev.has(b)) return null;
    const list = [b];
    for (let cur = b; prev.get(cur) !== null; cur = prev.get(cur)) list.push(prev.get(cur));
    list.reverse();
    const edges = new Set();
    for (let k = 1; k < list.length; k++) edges.add(graph.edge(list[k - 1], list[k]));
    return { nodes: new Set(list), edges, list, center: null, color: C.accent };
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

  function chip(i) {
    return `<button class="chip" data-id="${i}"><span class="dot" style="background:${color(i)}"></span><span>${esc(N.label[i])}</span></button>`;
  }
  function kv(pairs) {
    const rows = pairs.filter(([, v]) => v !== null && v !== undefined && v !== "");
    if (!rows.length) return "";
    return `<dl class="kv">${rows.map(([k, v]) => `<dt title="${esc(k)}">${esc(k)}</dt><dd>${esc(fmt(v))}</dd>`).join("")}</dl>`;
  }
  function showNodePanel(key) {
    const i = Number(key);
    $("panel-dot").style.background = color(i);
    $("panel-dot").hidden = false;
    $("panel-title").textContent = N.label[i];
    $("btn-pin").hidden = false;
    $("btn-pin").classList.toggle("on", !!graph.getNodeAttribute(key, "pinned"));
    const metrics = Object.keys(N.metrics).map((k) => [k, N.metrics[k][i]]);
    if (groupCount > 1 && !(cfg.groupName in N.metrics) && !(cfg.groupTitle in N.attrs)) {
      metrics.push([cfg.groupName, G.label[N.grp[i]]]);
    }
    let html = `<div class="section-title">${T.metrics}</div>${kv(metrics)}`;
    const attrs = kv(Object.keys(N.attrs).map((k) => [k, N.attrs[k][i]]));
    if (attrs) html += `<div class="section-title">${T.attributes}</div>${attrs}`;
    const nbrs = [...new Set(nbList.subarray(nbStart[i], nbStart[i + 1]))].filter((j) => j !== i);
    if (nbrs.length) {
      nbrs.sort((a, b) => N.size[b] - N.size[a]);
      const shown = nbrs.slice(0, 80);
      html += `<div class="section-title">${T.neighbors} <span class="muted">${fmt(nbrs.length)}</span></div><div class="chips">${shown.map(chip).join("")}`;
      if (nbrs.length > shown.length) html += `<span class="muted">+${fmt(nbrs.length - shown.length)}</span>`;
      html += "</div>";
    }
    $("panel-body").innerHTML = html;
    $("panel").hidden = false;
  }
  function showPathPanel(p) {
    $("panel-dot").hidden = true;
    $("panel-title").textContent = `${p.list.length - 1} ${p.list.length === 2 ? T.step : T.steps}`;
    $("btn-pin").hidden = true;
    $("panel-body").innerHTML = `<div class="section-title">${T.pathTitle}</div><div class="chips">${p.list.map((k) => chip(Number(k))).join(ICON.chevron)}</div>`;
    $("panel").hidden = false;
  }
  // plain-language findings; clicking one lights up the nodes it talks about
  const groupColor = (label) => {
    const gi = G.key.indexOf(label);
    return cfg.groupTitle === "community" && gi >= 0 ? G.color[gi] : null;
  };
  function showInsights(active) {
    state.selected = null;
    state.path = null;
    $("panel-dot").hidden = true;
    $("panel-title").textContent = T.insights;
    $("btn-pin").hidden = true;
    $("panel-body").innerHTML = `<div class="findings">${tarecoInsightsHtml(insights, groupColor, esc)}</div>`;
    if (active !== undefined) markFinding(active);
    $("panel").hidden = false;
    update();
  }
  function markFinding(k) {
    for (const el of document.querySelectorAll(".finding")) el.classList.toggle("on", el.dataset.k === String(k));
  }
  function spotlight(k) {
    const f = insights[k];
    if (!f.nodes.length) return;
    const gi = f.kind === "group" && cfg.groupTitle === "community" ? G.key.indexOf(f.group) : -1;
    if (gi >= 0 && groupCount > 1) {
      buildView({ kind: "group", g: gi });
      showInsights(k);
      return;
    }
    if (state.view.kind === "overview" || f.nodes.some((i) => !inView[i])) {
      buildView({ kind: "all" });
      showInsights(k);
    }
    const keys = f.nodes.map(String).filter((key) => graph.hasNode(key));
    const set = new Set(keys);
    const edges = new Set();
    for (const key of keys) {
      for (const e of graph.edges(key)) {
        if (set.has(graph.source(e)) && set.has(graph.target(e))) edges.add(e);
      }
    }
    state.spot = { nodes: set, edges, center: null, color: C.accent };
    markFinding(k);
    update();
    fitKeys(keys);
  }
  $("panel-body").addEventListener("click", (e) => {
    const b = e.target.closest(".chip");
    if (b) return select(reveal(Number(b.dataset.id)));
    const f = e.target.closest("button.finding");
    if (f) spotlight(Number(f.dataset.k));
  });
  $("btn-insights").hidden = insights.length === 0;
  $("btn-insights").onclick = () => showInsights();
  $("btn-close").onclick = clearAll;
  $("btn-pin").onclick = () => { if (state.selected) setPinned(state.selected, !graph.getNodeAttribute(state.selected, "pinned")); };

  // ---------------------------------------------------------------- toolbar

  function setPhysicsButton(running) {
    const b = $("btn-physics");
    b.classList.toggle("on", !running);
    b.dataset.tip = running ? T.freeze : T.resume;
  }
  $("btn-fit").onclick = () => {
    renderer.setCustomBBox(null);
    renderer.getCamera().animatedReset({ duration: 500 });
  };
  $("btn-labels").onclick = (e) => {
    state.labels = !state.labels;
    e.currentTarget.classList.toggle("on", state.labels);
    renderer.setSetting("renderLabels", state.labels);
  };
  $("btn-physics").onclick = () => {
    if (layout.running) { layout.pause(); setPhysicsButton(false); }
    else { layout.resume(0.4); setPhysicsButton(true); }
  };
  $("btn-path").onclick = () => setPathMode(!state.pathMode);
  $("btn-groups").hidden = groupCount < 2;
  $("btn-groups").onclick = () => buildView(state.view.kind === "overview" ? { kind: "all" } : { kind: "overview" });
  $("crumb-back").onclick = () => buildView({ kind: "overview" });
  $("btn-theme").onclick = () => {
    theme = theme === "dark" ? "light" : "dark";
    try { localStorage.setItem("tareco-theme", theme); } catch (e) { /* sandboxed */ }
    applyTheme();
    renderer.setSetting("labelColor", { color: C.text });
    if (state.view.kind === "overview") {
      const wmax = Math.max(1, ...G.w);
      graph.updateEachEdgeAttributes((key, attr) => { attr.color = withAlpha(C.edge, 0.03 + 0.6 * attr.w / wmax); return attr; }, { attributes: ["color"] });
    } else {
      edgeColor = withAlpha(C.edge, edgeAlpha(graph.size));
      graph.updateEachEdgeAttributes((key, attr) => { attr.color = edgeColor; return attr; }, { attributes: ["color"] });
    }
    update();
  };

  // ----------------------------------------------------------------- header

  $("title").textContent = cfg.title || "";
  function counted(shown, total, word) {
    return shown < total ? `${fmt(shown)} ${T.of} ${fmt(total)} ${word}` : `${fmt(total)} ${word}`;
  }
  function renderCounts() {
    const t = cfg.total;
    $("counts").textContent = state.view.kind === "overview"
      ? `${fmt(groupCount)} ${T.groupsWord} \u00b7 ${fmt(t.nodes)} ${T.nodes}`
      : `${counted(cfg.counts.nodes, t.nodes, T.nodes)} \u00b7 ${counted(cfg.counts.edges, t.edges, T.edges)}`;
  }
  function renderCrumb() {
    const v = state.view;
    $("crumb").hidden = v.kind !== "group";
    if (v.kind !== "group") return;
    $("crumb-dot").style.background = G.color[v.g];
    $("crumb-name").textContent = G.label[v.g];
    const note = G.note[v.g];
    $("crumb-count").textContent = counted(G.shown[v.g], G.size[v.g], T.nodes) + (note ? ` \u00b7 ${note}` : "");
  }

  // ----------------------------------------------------------------- search

  const input = $("search"), results = $("results");
  let hits = [], active = 0;
  function renderResults() {
    results.hidden = hits.length === 0;
    results.innerHTML = hits.map((i, k) =>
      `<li data-id="${i}" class="${k === active ? "active" : ""}"><span class="dot" style="background:${color(i)}"></span>${esc(N.label[i])}</li>`).join("");
  }
  input.addEventListener("input", () => {
    const q = norm(input.value.trim());
    active = 0;
    if (!q) { hits = []; renderResults(); return; }
    if (!searchKeys) searchKeys = N.label.map(norm);
    const found = [];
    for (let i = 0; i < n && found.length < 400; i++) if (searchKeys[i].includes(q)) found.push(i);
    hits = found.sort((a, b) => (searchKeys[b].startsWith(q) - searchKeys[a].startsWith(q)) || N.size[b] - N.size[a]).slice(0, 8);
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
    if (li) { e.preventDefault(); pick(Number(li.dataset.id)); }
  });
  input.addEventListener("blur", () => { results.hidden = true; });
  input.addEventListener("focus", () => { if (hits.length) results.hidden = false; });
  function pick(i) {
    input.value = ""; hits = []; renderResults(); input.blur();
    if (state.view.kind === "overview") buildView({ kind: "group", g: N.grp[i] });
    const key = reveal(i);
    if (state.pathMode) pathClick(key); else select(key);
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
  function renderLegend() {
    const box = $("legend");
    let html = "";
    if (legend && legend.kind === "category") {
      const items = legendAll ? legend.items : legend.items.slice(0, LEGEND_LIMIT);
      html += legend.title ? `<div class="legend-title">${esc(legend.title)}</div>` : "";
      html += items.map((it, k) => {
        const name = it.missing ? `<span class="none">${T.none}</span>` : esc(it.label) + (it.note ? `<span class="note">${esc(it.note)}</span>` : "");
        return `<button class="legend-item${state.hidden.has(k) ? " off" : ""}" data-k="${k}"><span class="dot" style="background:${it.color}"></span><span class="name">${name}</span><span class="count">${fmt(it.count)}</span></button>`;
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
  function refreshVisibility() {
    if (state.selected && graph.hasNode(state.selected) && hiddenNode(graph.getNodeAttributes(state.selected))) clearAll();
    else update();
    renderLegend();
  }
  $("legend").addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    if (b.dataset.more) { legendAll = !legendAll; renderLegend(); return; }
    const k = Number(b.dataset.k);
    if (state.hidden.has(k)) state.hidden.delete(k); else state.hidden.add(k);
    refreshVisibility();
  });
  $("legend").addEventListener("dblclick", (e) => {
    const b = e.target.closest(".legend-item");
    if (!b) return;
    const k = Number(b.dataset.k);
    const keys = legend.items.map((_, j) => j);
    const solo = keys.every((j) => (j === k) !== state.hidden.has(j));
    state.hidden = solo ? new Set() : new Set(keys.filter((j) => j !== k));
    refreshVisibility();
  });

  addEventListener("resize", () => { if (renderer) renderer.refresh(); });

  buildView({ kind: cfg.start === "overview" && groupCount > 1 ? "overview" : "all" });
})();

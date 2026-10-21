/* Force layout for big graphs, in the spirit of d3-force: springs on the edges,
   Barnes-Hut repulsion between nodes and a little gravity. It works on typed
   arrays and has no outside references, so the same function runs inside a Web
   Worker (via toString) or, when workers are blocked, on the main thread in
   small slices. */
function tarecoLayout(input) {
  "use strict";
  const n = input.n;
  const x = Float64Array.from(input.x);
  const y = Float64Array.from(input.y);
  const vx = new Float64Array(n);
  const vy = new Float64Array(n);
  const fixed = new Uint8Array(n);
  const edges = input.edges;
  const m = edges.length >> 1;
  const radius = input.radius;

  const deg = new Float64Array(n);
  for (let e = 0; e < m; e++) { deg[edges[2 * e]]++; deg[edges[2 * e + 1]]++; }
  const strength = new Float64Array(m);
  const bias = new Float64Array(m);
  const dist = new Float64Array(m);
  for (let e = 0; e < m; e++) {
    const s = edges[2 * e], t = edges[2 * e + 1];
    strength[e] = (input.edgeStrength ? input.edgeStrength[e] : 1) / Math.min(deg[s], deg[t]);
    bias[e] = deg[s] / (deg[s] + deg[t]);
    dist[e] = input.linkDistance + radius[s] + radius[t];
  }
  const charge = new Float64Array(n);
  for (let i = 0; i < n; i++) charge[i] = -(input.charge + input.chargePerArea * radius[i] * radius[i]);

  // optional pull toward the centre of each node's group, so communities read as islands
  const group = input.group || null;
  const groupPull = input.groupPull || 0;
  let groupCount = 0;
  if (group) for (let i = 0; i < n; i++) if (group[i] + 1 > groupCount) groupCount = group[i] + 1;
  const gsx = new Float64Array(groupCount), gsy = new Float64Array(groupCount), gnum = new Float64Array(groupCount);

  const theta2 = 0.81;
  const distMin2 = 1;
  const gravity = input.gravity;
  const velocityDecay = 0.6;
  const alphaMin = 0.001;
  const alphaDecay = 1 - Math.pow(alphaMin, 1 / (input.ticks || 300));
  let alpha = input.alpha || 1;

  let seed = 12345;
  function jiggle() {
    seed = (seed * 1664525 + 1013904223) >>> 0;
    return (seed / 4294967296 - 0.5) * 1e-6;
  }

  // quadtree in flat arrays; children of a quad are four consecutive slots
  let cap = 0, qn = 0;
  let qx0, qy0, qw, qcx, qcy, qs, qchild, qpoint;
  const pnext = new Int32Array(n);
  function grow(need) {
    if (need <= cap) return;
    const size = Math.max(need, cap * 2, 64);
    const f64 = (a) => { const b = new Float64Array(size); if (a) b.set(a.subarray(0, qn)); return b; };
    const i32 = (a) => { const b = new Int32Array(size); if (a) b.set(a.subarray(0, qn)); return b; };
    qx0 = f64(qx0); qy0 = f64(qy0); qw = f64(qw); qcx = f64(qcx); qcy = f64(qcy); qs = f64(qs);
    qchild = i32(qchild); qpoint = i32(qpoint);
    cap = size;
  }
  function quad(x0, y0, w) {
    grow(qn + 1);
    qx0[qn] = x0; qy0[qn] = y0; qw[qn] = w;
    qchild[qn] = -1; qpoint[qn] = -1; qs[qn] = 0; qcx[qn] = 0; qcy[qn] = 0;
    return qn++;
  }
  function insert(p) {
    let q = 0, depth = 0;
    for (;;) {
      const c = qchild[q];
      if (c >= 0) {
        const h = qw[q] / 2;
        q = c + (x[p] >= qx0[q] + h ? 1 : 0) + (y[p] >= qy0[q] + h ? 2 : 0);
        depth++;
        continue;
      }
      const o = qpoint[q];
      if (o < 0) { qpoint[q] = p; pnext[p] = -1; return; }
      if (depth >= 40 || (x[o] === x[p] && y[o] === y[p])) { pnext[p] = o; qpoint[q] = p; return; }
      const h = qw[q] / 2, x0 = qx0[q], y0 = qy0[q];
      const first = quad(x0, y0, h);
      quad(x0 + h, y0, h); quad(x0, y0 + h, h); quad(x0 + h, y0 + h, h);
      qchild[q] = first;
      qpoint[q] = -1;
      qpoint[first + (x[o] >= x0 + h ? 1 : 0) + (y[o] >= y0 + h ? 2 : 0)] = o;
    }
  }
  function buildTree() {
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    for (let i = 0; i < n; i++) {
      if (x[i] < x0) x0 = x[i]; if (x[i] > x1) x1 = x[i];
      if (y[i] < y0) y0 = y[i]; if (y[i] > y1) y1 = y[i];
    }
    qn = 0;
    quad(x0, y0, Math.max(x1 - x0, y1 - y0) + 1);
    for (let i = 0; i < n; i++) insert(i);
    for (let q = qn - 1; q >= 0; q--) {  // children always come after their parent
      let s = 0, sx = 0, sy = 0, aw = 0;
      if (qchild[q] >= 0) {
        for (let k = qchild[q]; k < qchild[q] + 4; k++) {
          if (qs[k] === 0) continue;
          const a = Math.abs(qs[k]);
          s += qs[k]; sx += qcx[k] * a; sy += qcy[k] * a; aw += a;
        }
      } else {
        for (let p = qpoint[q]; p >= 0; p = pnext[p]) {
          const a = Math.abs(charge[p]);
          s += charge[p]; sx += x[p] * a; sy += y[p] * a; aw += a;
        }
      }
      qs[q] = s;
      if (aw) { qcx[q] = sx / aw; qcy[q] = sy / aw; }
    }
  }
  const stack = new Int32Array(1024);
  function repel(i) {
    let sp = 0;
    stack[sp++] = 0;
    while (sp) {
      const q = stack[--sp];
      if (qs[q] === 0) continue;
      if (qchild[q] >= 0) {
        const dx = qcx[q] - x[i], dy = qcy[q] - y[i];
        let l = dx * dx + dy * dy;
        const w = qw[q];
        if (w * w / theta2 < l) {
          if (l < distMin2) l = Math.sqrt(distMin2 * l);
          const f = qs[q] * alpha / l;
          vx[i] += dx * f; vy[i] += dy * f;
        } else if (sp < stack.length - 4) {
          const c = qchild[q];
          stack[sp++] = c; stack[sp++] = c + 1; stack[sp++] = c + 2; stack[sp++] = c + 3;
        }
      } else {
        for (let p = qpoint[q]; p >= 0; p = pnext[p]) {
          if (p === i) continue;
          let dx = x[p] - x[i], dy = y[p] - y[i];
          if (dx === 0) dx = jiggle();
          if (dy === 0) dy = jiggle();
          let l = dx * dx + dy * dy;
          if (l < distMin2) l = Math.sqrt(distMin2 * l);
          const f = charge[p] * alpha / l;
          vx[i] += dx * f; vy[i] += dy * f;
        }
      }
    }
  }

  function tick() {
    alpha += -alpha * alphaDecay;
    for (let e = 0; e < m; e++) {
      const s = edges[2 * e], t = edges[2 * e + 1];
      let dx = x[t] + vx[t] - x[s] - vx[s] || jiggle();
      let dy = y[t] + vy[t] - y[s] - vy[s] || jiggle();
      let l = Math.sqrt(dx * dx + dy * dy);
      l = (l - dist[e]) / l * alpha * strength[e];
      dx *= l; dy *= l;
      const b = bias[e];
      vx[t] -= dx * b; vy[t] -= dy * b;
      vx[s] += dx * (1 - b); vy[s] += dy * (1 - b);
    }
    if (n > 1) {
      buildTree();
      for (let i = 0; i < n; i++) repel(i);
    }
    if (group && groupPull) {
      gsx.fill(0); gsy.fill(0); gnum.fill(0);
      for (let i = 0; i < n; i++) { const g = group[i]; gsx[g] += x[i]; gsy[g] += y[i]; gnum[g]++; }
      for (let i = 0; i < n; i++) {
        const g = group[i];
        vx[i] += (gsx[g] / gnum[g] - x[i]) * groupPull * alpha;
        vy[i] += (gsy[g] / gnum[g] - y[i]) * groupPull * alpha;
      }
    }
    for (let i = 0; i < n; i++) {
      if (fixed[i]) { vx[i] = vy[i] = 0; continue; }
      // nodes without edges would drift away on repulsion alone
      const pull = deg[i] ? gravity : gravity * 10;
      vx[i] -= x[i] * pull * alpha;
      vy[i] -= y[i] * pull * alpha;
      x[i] += (vx[i] *= velocityDecay);
      y[i] += (vy[i] *= velocityDecay);
    }
  }

  return {
    x, y, tick,
    alpha: () => alpha,
    done: () => alpha < alphaMin,
    reheat(a) { alpha = Math.max(alpha, a || 0.3); },
    pin(i, px, py) { fixed[i] = 1; x[i] = px; y[i] = py; vx[i] = vy[i] = 0; },
    unpin(i) { fixed[i] = 0; },
  };
}

/* Runs tarecoLayout off the main thread and reports positions through onFrame(x, y, done).
   Falls back to time-sliced work on the main thread when workers are not allowed. */
function tarecoRunLayout(input, onFrame) {
  "use strict";
  const workerSource = tarecoLayout.toString() + `
    let engine = null, running = false;
    function loop() {
      if (!engine || !running) return;
      const start = Date.now();
      do engine.tick(); while (Date.now() - start < 24 && !engine.done());
      const x = new Float32Array(engine.x), y = new Float32Array(engine.y);
      const done = engine.done();
      postMessage({ x, y, done }, [x.buffer, y.buffer]);
      if (done) running = false; else setTimeout(loop, 0);
    }
    onmessage = (e) => {
      const msg = e.data;
      if (msg.type === "init") { engine = tarecoLayout(msg.input); running = true; loop(); }
      else if (!engine) return;
      else if (msg.type === "pause") running = false;
      else if (msg.type === "resume") { engine.reheat(msg.alpha); if (!running) { running = true; loop(); } }
      else if (msg.type === "pin") engine.pin(msg.i, msg.x, msg.y);
      else if (msg.type === "unpin") engine.unpin(msg.i);
    };`;

  let worker = null, engine = null, running = true, stopped = false, frame = 0;
  const pins = [];

  function step() {
    frame = 0;
    if (stopped || !running) return;
    const start = performance.now();
    do engine.tick(); while (performance.now() - start < 10 && !engine.done());
    const done = engine.done();
    onFrame(engine.x, engine.y, done);
    if (done) running = false; else frame = requestAnimationFrame(step);
  }
  function local() {
    if (worker) { worker.terminate(); worker = null; }
    if (stopped || engine) return;
    engine = tarecoLayout(input);
    for (const [i, px, py] of pins) engine.pin(i, px, py);
    frame = requestAnimationFrame(step);
  }

  try {
    const url = URL.createObjectURL(new Blob([workerSource], { type: "text/javascript" }));
    worker = new Worker(url);
    worker.onmessage = (e) => {
      if (stopped) return;
      if (e.data.done) running = false;
      onFrame(e.data.x, e.data.y, e.data.done);
    };
    worker.onerror = (e) => { if (e && e.preventDefault) e.preventDefault(); local(); };
    worker.postMessage({ type: "init", input });
  } catch (err) {
    local();
  }

  return {
    get running() { return running; },
    get usesWorker() { return !!worker; },
    pause() {
      running = false;
      if (worker) worker.postMessage({ type: "pause" });
      else if (frame) { cancelAnimationFrame(frame); frame = 0; }
    },
    resume(alpha) {
      running = true;
      if (worker) worker.postMessage({ type: "resume", alpha });
      else if (engine) { engine.reheat(alpha); if (!frame) frame = requestAnimationFrame(step); }
    },
    pin(i, px, py) {
      pins.push([i, px, py]);
      if (worker) worker.postMessage({ type: "pin", i, x: px, y: py });
      else if (engine) engine.pin(i, px, py);
    },
    unpin(i) {
      for (let k = pins.length - 1; k >= 0; k--) if (pins[k][0] === i) pins.splice(k, 1);
      if (worker) worker.postMessage({ type: "unpin", i });
      else if (engine) engine.unpin(i);
    },
    stop() {
      stopped = true;
      running = false;
      if (worker) worker.terminate();
      if (frame) cancelAnimationFrame(frame);
    },
  };
}

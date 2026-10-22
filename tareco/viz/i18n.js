/* Interface text in English and Portuguese, shared by both views. */
function tarecoText(lang) {
  "use strict";
  const all = {
    en: {
      locale: "en-US",
      search: "Search",
      searchLabel: "Search nodes",
      fit: "Fit to screen",
      labels: "Labels",
      freeze: "Freeze layout",
      resume: "Resume layout",
      path: "Shortest path: click two nodes",
      groups: "Groups overview",
      insights: "Insights",
      theme: "Theme",
      save: "Save image",
      pin: "Pin in place",
      close: "Close",
      allGroups: "All groups",
      metrics: "Metrics",
      attributes: "Attributes",
      neighbors: "Neighbors",
      pathTitle: "Path",
      step: "step",
      steps: "steps",
      noPath: (a, b) => `No path from ${a} to ${b}`,
      nodes: "nodes",
      edges: "edges",
      groupsWord: "groups",
      of: "of",
      none: "none",
      more: (k) => `+${k} more`,
      less: "Less",
      allPeriods: "All periods",
      play: "Play",
      pause: "Pause",
      linkKinds: "Links",
      standsOut: "What stands out",
      rowsTitle: "Rows behind it",
      moreRows: (k) => `+${k} more rows`,
    },
    pt: {
      locale: "pt-BR",
      search: "Buscar",
      searchLabel: "Buscar n\u00f3s",
      fit: "Enquadrar",
      labels: "R\u00f3tulos",
      freeze: "Congelar layout",
      resume: "Retomar layout",
      path: "Caminho m\u00ednimo: clique em dois n\u00f3s",
      groups: "Vis\u00e3o por grupos",
      insights: "Destaques",
      theme: "Tema",
      save: "Salvar imagem",
      pin: "Fixar no lugar",
      close: "Fechar",
      allGroups: "Todos os grupos",
      metrics: "M\u00e9tricas",
      attributes: "Atributos",
      neighbors: "Vizinhos",
      pathTitle: "Caminho",
      step: "passo",
      steps: "passos",
      noPath: (a, b) => `N\u00e3o h\u00e1 caminho de ${a} at\u00e9 ${b}`,
      nodes: "n\u00f3s",
      edges: "conex\u00f5es",
      groupsWord: "grupos",
      of: "de",
      none: "nenhum",
      more: (k) => `+${k} outros`,
      less: "Menos",
      allPeriods: "Todos os per\u00edodos",
      play: "Reproduzir",
      pause: "Pausar",
      linkKinds: "Liga\u00e7\u00f5es",
      standsOut: "O que chama aten\u00e7\u00e3o",
      rowsTitle: "Linhas por tr\u00e1s",
      moreRows: (k) => `+${k} linhas`,
    },
  };
  const T = all[lang] || all.en;
  const tip = (id, text) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.dataset.tip = text;
    el.setAttribute("aria-label", text);
  };
  tip("btn-fit", T.fit);
  tip("btn-labels", T.labels);
  tip("btn-physics", T.freeze);
  tip("btn-path", T.path);
  tip("btn-groups", T.groups);
  tip("btn-insights", T.insights);
  tip("btn-theme", T.theme);
  tip("btn-png", T.save);
  tip("btn-pin", T.pin);
  tip("crumb-back", T.allGroups);
  const close = document.getElementById("btn-close");
  if (close) close.setAttribute("aria-label", T.close);
  const search = document.getElementById("search");
  if (search) { search.placeholder = T.search; search.setAttribute("aria-label", T.searchLabel); }
  document.documentElement.lang = lang === "pt" ? "pt-BR" : "en";
  return T;
}

/* The insights list in the side panel: plain-language findings, each one clickable when it is about nodes. */
/* What stands out about a node, one line per kind of signal. */
function tarecoNotesHtml(notes, esc) {
  "use strict";
  return `<ul class="notes">${notes.map((t) => `<li>${esc(t)}</li>`).join("")}</ul>`;
}

/* The rows of the user's table behind a finding, as a small scrollable table. */
function tarecoRowsHtml(finding, esc, fmt, T) {
  "use strict";
  const rows = finding.rows || [];
  if (!rows.length) return "";
  const cols = [];
  for (const r of rows) for (const k of Object.keys(r)) if (!cols.includes(k)) cols.push(k);
  const head = cols.map((c) => `<th>${esc(c)}</th>`).join("");
  const body = rows.map((r) => `<tr>${cols.map((c) => `<td>${esc(fmt(r[c]))}</td>`).join("")}</tr>`).join("");
  const more = finding.rowCount > rows.length ? `<div class="muted">${T.moreRows(finding.rowCount - rows.length)}</div>` : "";
  return `<div class="rows-box"><div class="section-title">${T.rowsTitle} <span class="muted">${fmt(finding.rowCount)}</span></div>` +
    `<div class="rows-scroll"><table class="rows"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>${more}</div>`;
}

function tarecoInsightsHtml(findings, colorOfGroup, esc) {
  "use strict";
  return findings.map((f, k) => {
    const dot = f.group && colorOfGroup(f.group) ? `<span class="dot" style="background:${colorOfGroup(f.group)}"></span>` : "";
    const tag = f.nodes && f.nodes.length ? "button" : "div";
    return `<${tag} class="finding finding-${f.kind}" data-k="${k}">${dot}<span>${esc(f.text)}</span></${tag}>`;
  }).join("");
}

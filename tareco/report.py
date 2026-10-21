"""One self-contained HTML file to send to someone: the findings, the tables and the graph."""

import html
import os

from . import i18n

STYLE = """
:root, :root[data-theme="light"] { --bg:#f6f7fb; --card:#fff; --text:#0f172a; --muted:#64748b;
  --border:rgba(15,23,42,.09); --accent:#0284c7; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --bg:#0b1020; --card:#111827;
  --text:#e5e7eb; --muted:#94a3b8; --border:rgba(148,163,184,.16); --accent:#38bdf8; } }
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--text);
  font:15px/1.6 ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, Arial, sans-serif; }
main { max-width: 1040px; margin: 0 auto; padding: 40px 16px 64px; }
h1 { font-size: 28px; margin: 0 0 4px; letter-spacing: -0.01em; }
h2 { font-size: 18px; margin: 36px 0 12px; }
.lead { color: var(--muted); margin: 0 0 24px; }
.card { background: var(--card); border: 1px solid var(--border); border-radius: 14px; padding: 18px 20px; }
ul.findings { margin: 0; padding-left: 20px; }
ul.findings li { margin: 6px 0; }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th { text-align: left; color: var(--muted); font-weight: 600; font-size: 12px; text-transform: uppercase;
  letter-spacing: .05em; padding: 8px 10px; border-bottom: 1px solid var(--border); }
td { padding: 8px 10px; border-bottom: 1px solid var(--border); vertical-align: top; }
td.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
.scroll { overflow-x: auto; }
.tareco-graph iframe { border: 1px solid var(--border) !important; display: block; }
"""

HEADINGS = {
    "en": {"findings": "What this network shows", "groups": "Groups", "top": "Most important nodes",
           "patterns": "Patterns", "activity": "Activity over time", "graph": "Explore the network",
           "group": "Group", "size": "Nodes", "share": "Share", "traits": "What sets it apart",
           "members": "Key members", "inward": "Inside", "node": "Node", "importance": "Importance",
           "connections": "Connections", "period": "Period", "active": "Active nodes",
           "weight": "Weight", "lead": "{n} nodes and {m} connections"},
    "pt": {"findings": "O que esta rede mostra", "groups": "Grupos", "top": "Nós mais importantes",
           "patterns": "Padrões", "activity": "Atividade ao longo do tempo", "graph": "Explore a rede",
           "group": "Grupo", "size": "Nós", "share": "Parcela", "traits": "O que o distingue",
           "members": "Principais membros", "inward": "Dentro", "node": "Nó", "importance": "Importância",
           "connections": "Conexões", "period": "Período", "active": "Nós ativos",
           "weight": "Peso", "lead": "{n} nós e {m} conexões"},
}


def report(g, path=None, title=None, lang=None, label=None, timeline=None, height=640, **view):
    """The findings, the group and node tables and the interactive graph, in one file.

    Returns the file path when ``path`` is given, otherwise the HTML text.
    """
    from .viz import notebook_html
    lang = i18n.get_language(lang)
    H = HEADINGS[lang]
    num = lambda v: i18n.number(v, lang)  # noqa: E731
    title = title or g.attrs.get("title") or ("Network report" if lang == "en" else "Relatório da rede")
    exp = timeline.explain(lang=lang, label=label) if timeline is not None else g.explain(lang=lang, label=label)
    parts = [f"<h1>{_e(title)}</h1>",
             f'<p class="lead">{_e(H["lead"].format(n=num(len(g)), m=num(g.edge_count)))}</p>',
             f'<h2>{_e(H["findings"])}</h2><div class="card"><ul class="findings">'
             + "".join(f"<li>{_e(f.text)}</li>" for f in exp.findings) + "</ul></div>"]

    profiles = [p for p in exp.profiles if p.size >= 2]
    if profiles:
        rows = "".join(
            f"<tr><td>{_e(p.name)}</td><td class='num'>{num(p.size)}</td>"
            f"<td class='num'>{i18n.percent(p.share, lang)}</td><td>{_e(p.summary(limit=3))}</td>"
            f"<td>{_e(i18n.join(p.key_members, lang))}</td>"
            f"<td class='num'>{i18n.percent(p.inward, lang) if p.inward is not None else ''}</td></tr>"
            for p in profiles[:30])
        parts.append(f'<h2>{_e(H["groups"])}</h2><div class="card scroll"><table><tr>'
                     f'<th>{_e(H["group"])}</th><th>{_e(H["size"])}</th><th>{_e(H["share"])}</th>'
                     f'<th>{_e(H["traits"])}</th><th>{_e(H["members"])}</th><th>{_e(H["inward"])}</th>'
                     f"</tr>{rows}</table></div>")

    if g.edge_count:
        rank = g.pagerank()
        degree = g.degree()
        group_of = {x: p.name for p in exp.profiles for x in p.members}
        top = sorted(g, key=lambda x: -rank[x])[:10]
        rows = "".join(
            f"<tr><td>{_e(_name(g, x, label))}</td><td class='num'>{i18n.percent(rank[x], lang)}</td>"
            f"<td class='num'>{num(degree[x])}</td><td>{_e(group_of.get(x, ''))}</td></tr>" for x in top)
        parts.append(f'<h2>{_e(H["top"])}</h2><div class="card scroll"><table><tr>'
                     f'<th>{_e(H["node"])}</th><th>{_e(H["importance"])}</th>'
                     f'<th>{_e(H["connections"])}</th><th>{_e(H["group"])}</th></tr>{rows}</table></div>')

    found = g.patterns(lang=lang, label=label, limit=3)
    if found:
        parts.append(f'<h2>{_e(H["patterns"])}</h2><div class="card"><ul class="findings">'
                     + "".join(f"<li>{_e(p.text)}</li>" for p in found) + "</ul></div>")

    if timeline is not None:
        rows = "".join(
            f"<tr><td>{_e(a['period'])}</td><td class='num'>{num(a['nodes'])}</td>"
            f"<td class='num'>{num(a['connections'])}</td><td class='num'>{num(a['weight'])}</td></tr>"
            for a in timeline.activity())
        parts.append(f'<h2>{_e(H["activity"])}</h2><div class="card scroll"><table><tr>'
                     f'<th>{_e(H["period"])}</th><th>{_e(H["active"])}</th>'
                     f'<th>{_e(H["connections"])}</th><th>{_e(H["weight"])}</th></tr>{rows}</table></div>')

    budget = view.pop("budget_mb", None) or 50
    options = dict(view, lang=lang, label=label, title=title, insights=exp)
    if timeline is not None:
        options["time"] = timeline._time_info()
    frame = notebook_html(g, height=height, budget_mb=budget, **options)
    parts.append(f'<h2>{_e(H["graph"])}</h2>{frame}')

    page = (f'<!doctype html><html lang="{"pt-BR" if lang == "pt" else "en"}"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1"><title>{_e(title)}</title>'
            f"<style>{STYLE}</style></head><body><main>{''.join(parts)}</main></body></html>")
    page = page.encode("ascii", "xmlcharrefreplace").decode("ascii")
    if path is None:
        return page
    with open(path, "w", encoding="utf-8") as f:
        f.write(page)
    return os.path.abspath(path)


def _e(text):
    return html.escape(str(text))


def _name(g, node, label):
    if label is not None:
        value = g.nodes[node].get(label)
        if value is not None:
            return str(value)
    return str(node)

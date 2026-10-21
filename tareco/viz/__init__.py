"""Interactive HTML views: a force-directed graph you can drag, search and explore.

Small graphs are drawn with force-graph on a canvas. Big ones switch to a WebGL
renderer (sigma.js) whose layout runs in a Web Worker, so the page never
freezes, and very big ones are trimmed to their most important part, with an
overview where each group of nodes is one bubble you can open.
"""

import colorsys
import html
import json
import math
import os
import random
import re
import sys
import tempfile
import webbrowser
from decimal import Decimal
from importlib import resources

from .. import i18n
from ..errors import TarecoError
from ..io import json_default

PALETTE = ["#6366f1", "#f43f5e", "#10b981", "#f59e0b", "#06b6d4", "#a855f7",
           "#84cc16", "#ec4899", "#14b8a6", "#f97316", "#3b82f6", "#eab308"]
GRADIENT = ["#3b82f6", "#8b5cf6", "#ec4899", "#f97316", "#facc15"]
MISSING_COLOR = "#94a3b8"
METRICS = ("pagerank", "degree", "betweenness", "closeness", "clustering", "core",
           "community", "component")
GROUP_METRICS = ("community", "component")
LIB_3D = "https://cdn.jsdelivr.net/npm/3d-force-graph@1.80.1/dist/3d-force-graph.min.js"

CANVAS_LIMIT = (2_000, 8_000)        # "auto" switches to WebGL above this many nodes/edges
CANVAS_MAX = (3_000, 12_000)         # what the canvas and 3D views embed by default
WEBGL_MAX = (50_000, 200_000)        # what the WebGL view embeds by default
OVERVIEW_START = (30_000, 120_000)   # the WebGL view opens on the group overview above this
MAX_GROUPS = 250                     # bubbles in the overview; smaller groups are merged
MAX_ATTR_COLUMNS = 40
SAMPLED_BETWEENNESS = (2_000, 500)   # above 2,000 nodes, estimate betweenness from 500 sources
CLOSENESS_LIMIT = 20_000
DATABRICKS_BUDGET_MB = 9             # cell output is cut at 10 MB by default on DBR 17+
NOTEBOOK_BUDGET_MB = 25


# ---------------------------------------------------------------------- public

def to_html(g, color=None, size=None, label=None, edge_width=None, title=None, dim=2,
            particles=False, theme="auto", renderer="auto", max_nodes=None, max_edges=None,
            budget_mb=None, lang=None, insights=True):
    """The interactive view as a standalone HTML document (string).

    color       attribute name, a metric ("community", "pagerank", "degree",
                "betweenness", "closeness", "clustering", "core", "component"),
                a {node: value} dict, a function of the node, or one CSS color.
                Defaults to "community".
    size        same kinds of values (numbers); defaults to "pagerank".
    label       attribute holding the text shown for each node (default: the id).
    edge_width  edge attribute for line width (default: "weight" when present).
    dim         2 or 3. The 3D view loads its library from a CDN.
    particles   animated dots flowing along the edges (canvas and 3D views).
    theme       "auto", "dark" or "light".
    renderer    "auto" (canvas for small graphs, WebGL above 2,000 nodes or
                8,000 edges), "canvas" or "webgl".
    max_nodes   most nodes to embed; bigger graphs keep their highest-PageRank
    max_edges   nodes (and heaviest edges). Defaults: 50,000/200,000 for WebGL,
                3,000/12,000 for canvas and 3D.
    budget_mb   shrink the graph until the page fits in this many megabytes.
    lang        "en" or "pt" for the interface and the insights (default:
                tareco.set_language, else English).
    insights    add the plain-language findings of ``explain()`` to the view.
    """
    return _build(g, dict(color=color, size=size, label=label, edge_width=edge_width,
                          title=title, dim=dim, particles=particles, theme=theme,
                          lang=lang, insights=insights),
                  renderer, max_nodes, max_edges, budget_mb, wrap=None)


def save(g, path, **options):
    """Write the view to ``path`` and return the absolute path."""
    with open(path, "w", encoding="utf-8") as f:
        f.write(to_html(g, **options))
    return os.path.abspath(path)


def notebook_html(g, height=560, budget_mb=None, renderer="auto", max_nodes=None,
                  max_edges=None, **options):
    """The view wrapped in an iframe for notebook output, kept under ``budget_mb``."""
    if budget_mb is None:
        budget_mb = default_budget_mb()

    def wrap(doc):
        # a bare <iframe> makes IPython warn; the div keeps the output quiet
        return (f'<div class="tareco-graph"><iframe srcdoc="{html.escape(doc, quote=True)}" '
                f'style="width:100%;height:{int(height)}px;border:0;border-radius:12px" '
                f'sandbox="allow-scripts allow-downloads"></iframe></div>')

    return _build(g, options, renderer, max_nodes, max_edges, budget_mb, wrap)


def show(g, height=560, **options):
    """Inline in Jupyter, VS Code, Colab and Databricks; otherwise opens the browser.

    Where there is neither a notebook nor a browser (a cluster job, a server),
    the page is saved to a temporary file and its path is printed.
    """
    if _in_notebook() or _on_databricks():
        if _display_html(notebook_html(g, height=height, **options)):
            return
    folder = os.path.join(tempfile.gettempdir(), "tareco")
    os.makedirs(folder, exist_ok=True)
    fd, path = tempfile.mkstemp(suffix=".html", prefix="graph-", dir=folder)
    os.close(fd)
    save(g, path, **options)
    opened = False
    if not _on_databricks():
        try:
            opened = webbrowser.open("file://" + os.path.abspath(path).replace(os.sep, "/"))
        except Exception:
            opened = False
    if not opened:
        print(f"tareco: no browser here, the graph was saved to {path}")


def default_budget_mb():
    return DATABRICKS_BUDGET_MB if _on_databricks() else NOTEBOOK_BUDGET_MB


# ------------------------------------------------------------------ environment

def _in_notebook():
    shell = _ipython()
    return shell is not None and getattr(shell, "kernel", None) is not None


def _on_databricks():
    return "DATABRICKS_RUNTIME_VERSION" in os.environ


def _ipython():
    ipython = sys.modules.get("IPython")
    if ipython is None:
        return None
    try:
        return ipython.get_ipython()
    except Exception:
        return None


def _display_html(markup):
    """Render HTML in the current notebook. False when there is no way to."""
    shell = _ipython()
    namespace = getattr(shell, "user_ns", None) or {}
    display_html = namespace.get("displayHTML") or getattr(sys.modules.get("__main__"), "displayHTML", None)
    if display_html is not None:  # Databricks
        display_html(markup)
        return True
    if shell is not None:
        from IPython.display import HTML, display
        display(HTML(markup))
        return True
    return False


def _asset(name):
    return resources.files(__name__).joinpath(name).read_text(encoding="utf-8")


# ---------------------------------------------------------------------- build

def _choose_renderer(g, renderer, dim):
    if renderer not in ("auto", "canvas", "webgl"):
        raise TarecoError('renderer must be "auto", "canvas" or "webgl"')
    if dim not in (2, 3):
        raise TarecoError("dim must be 2 or 3")
    if dim == 3:
        if renderer == "webgl":
            raise TarecoError("the WebGL renderer is 2D; use dim=2 or renderer='auto'")
        return "3d"
    if renderer == "auto":
        big = len(g) > CANVAS_LIMIT[0] or g.edge_count > CANVAS_LIMIT[1]
        return "webgl" if big else "canvas"
    return renderer


def _build(g, options, renderer, max_nodes, max_edges, budget_mb, wrap):
    kind = _choose_renderer(g, renderer, options.get("dim", 2))
    limits = WEBGL_MAX if kind == "webgl" else CANVAS_MAX
    max_nodes = limits[0] if max_nodes is None else max_nodes
    max_edges = limits[1] if max_edges is None else max_edges
    metric = _metric_cache(g)
    for _ in range(6):
        doc, shown = _document(g, kind, options, max_nodes, max_edges, metric)
        out = wrap(doc) if wrap else doc
        size = len(out.encode("utf-8"))
        if not budget_mb or size <= budget_mb * 1e6 or shown == (0, 0):
            return out
        ratio = budget_mb * 1e6 / size * 0.85
        max_nodes = max(10, int(shown[0] * ratio))
        max_edges = max(10, int(shown[1] * ratio))
    return out


def _document(g, kind, options, max_nodes, max_edges, metric):
    nodes, triples = _reduce(g, max_nodes, max_edges, metric)
    if kind == "webgl":
        payload = build_webgl_payload(g, nodes, triples, metric, **options)
        lib = "".join(f"<script>{_asset(name)}</script>"
                      for name in ("graphology.umd.min.js", "sigma.min.js"))
        app = _asset("i18n.js") + "\n" + _asset("layout.js") + "\n" + _asset("webgl.js")
    else:
        payload = build_payload(g, nodes, triples, metric, **options)
        if kind == "3d":
            lib = f'<script src="{LIB_3D}"></script>'
        else:
            lib = "<script>" + _asset("force-graph.min.js") + "</script>"
        app = _asset("i18n.js") + "\n" + _asset("app.js")
    # ASCII only: the page may be embedded in a notebook that decodes it with any charset
    data = json.dumps(payload, default=json_default, ensure_ascii=True,
                      separators=(",", ":")).replace("<", "\\u003c")
    title = html.escape(payload["config"]["title"] or "tareco")
    parts = {
        "__TITLE__": title.encode("ascii", "xmlcharrefreplace").decode("ascii"),
        "<!--LIB-->": lib,
        "/*DATA*/": "window.__TARECO__ = " + data + ";",
        "/*STYLE*/": _asset("style.css"),
        "/*APP*/": app,
    }
    # one pass, so inserted text is never scanned for markers again
    page = re.sub("|".join(re.escape(k) for k in parts), lambda m: parts[m.group(0)],
                  _asset("template.html"))
    return page, (len(nodes), len(triples))


def _metric_cache(g):
    cache = {}

    def metric(name):
        if name not in cache:
            cache[name] = _compute_metric(g, name)
        return cache[name]

    return metric


def _compute_metric(g, name):
    n = len(g)
    if name == "pagerank":
        return g.pagerank()
    if name == "degree":
        return g.degree()
    if name == "betweenness":
        above, k = SAMPLED_BETWEENNESS
        return g.betweenness(k=k if n > above else None)
    if name == "closeness":
        if n > CLOSENESS_LIMIT:
            raise TarecoError(f"closeness needs a search from every node, too slow for {n:,} "
                              f"nodes; try 'pagerank' or 'betweenness'")
        return g.closeness()
    if name == "clustering":
        return g.clustering()
    if name == "core":
        return g.core_number()
    groups = g.communities() if name == "community" else g.components()
    return {node: i + 1 for i, members in enumerate(groups) for node in members}


def _reduce(g, max_nodes, max_edges, metric):
    """Nodes and edges to embed: everything, or the most important part."""
    nodes = list(g)
    if len(nodes) <= max_nodes and g.edge_count <= max_edges:
        return nodes, list(g._edge_triples())
    rank = metric("pagerank")
    if len(nodes) > max_nodes:
        keep = set(sorted(nodes, key=rank.get, reverse=True)[:max_nodes])
        nodes = [n for n in nodes if n in keep]
        triples = [t for t in g._edge_triples() if t[0] in keep and t[1] in keep]
    else:
        triples = list(g._edge_triples())
    if len(triples) > max_edges:
        def importance(t):
            w = _number(t[2].get("weight"))
            return (w if w is not None else 1.0, rank[t[0]] + rank[t[1]])
        triples = sorted(triples, key=importance, reverse=True)[:max_edges]
    return nodes, triples


def _defaults(g, color, size):
    if color is None:
        color = "community" if g.edge_count else None
    if size is None:
        size = "pagerank" if g.edge_count else None
    return color, size


def _edge_width_attr(edge_width, triples):
    if edge_width is None and any(_number(d.get("weight")) is not None for _, _, d in triples):
        return "weight"
    return edge_width


def _config(g, nodes, triples, title, theme, legend, size, **extra):
    config = {
        "title": title if title is not None else g.attrs.get("title", ""),
        "directed": g.directed,
        "theme": theme,
        "legend": legend,
        "size": size if isinstance(size, str) else None,
        "counts": {"nodes": len(nodes), "edges": len(triples)},
        "total": {"nodes": len(g), "edges": g.edge_count},
    }
    config.update(extra)
    return config


# ------------------------------------------------------------- canvas payload

def build_payload(g, nodes=None, triples=None, metric=None, color=None, size=None, label=None,
                  edge_width=None, title=None, dim=2, particles=False, theme="auto", lang=None,
                  insights=True):
    """Data for the canvas/3D view: one object per node and per link."""
    if nodes is None:
        nodes = list(g)
    if triples is None:
        triples = list(g._edge_triples())
    metric = metric or _metric_cache(g)
    color, size = _defaults(g, color, size)
    colors, groups, legend = _colors(g, nodes, color, metric)
    lang, findings, notes, _ = _insights(g, nodes, metric, legend, color, lang, label, insights)
    sizes = _sizes(g, nodes, size, metric)
    shown = _shown_metrics(g, color, size, metric)
    edge_width = _edge_width_attr(edge_width, triples)
    widths = _scale([_number(d.get(edge_width)) if edge_width else None for _, _, d in triples],
                    0.6, 5.0, 1.0)

    index = {n: i for i, n in enumerate(nodes)}
    pairs = {(u, v) for u, v, _ in triples} if g.directed else set()
    out_nodes = []
    for i, n in enumerate(nodes):
        attrs = g.nodes[n]
        out_nodes.append({
            "id": i,
            "label": _label(n, attrs, label),
            "color": colors[i],
            "val": sizes[i],
            "group": groups[i],
            "attrs": attrs,
            "metrics": {i18n.metric_name(k, lang): v[n] for k, v in shown.items()},
        })
    out_links = []
    for (u, v, d), w in zip(triples, widths):
        curve = 0.6 if u == v else 0.18 if (v, u) in pairs else 0.0
        out_links.append({"source": index[u], "target": index[v], "w": w, "curve": curve, "attrs": d})

    return {
        "config": _localize(_config(g, nodes, triples, title, theme, legend, size, renderer="canvas",
                                    dim=dim, particles=bool(particles), lang=lang, insights=findings),
                            lang),
        "nodes": out_nodes,
        "links": out_links,
    }


def _shown_metrics(g, color, size, metric):
    shown = {"in": g.in_degree(), "out": g.out_degree()} if g.directed else {"degree": g.degree()}
    for name in (color, size):
        if isinstance(name, str) and name in METRICS:
            shown[name] = metric(name)
    return shown


def _label(node, attrs, label):
    text = attrs.get(label) if label is not None else None
    return str(node if text is None else text)


# -------------------------------------------------------------- WebGL payload

def build_webgl_payload(g, nodes=None, triples=None, metric=None, color=None, size=None,
                        label=None, edge_width=None, title=None, dim=2, particles=False,
                        theme="auto", lang=None, insights=True):
    """Data for the WebGL view, column by column to keep big pages small."""
    if nodes is None:
        nodes = list(g)
    if triples is None:
        triples = list(g._edge_triples())
    metric = metric or _metric_cache(g)
    color, size = _defaults(g, color, size)
    colors, cats, legend = _colors(g, nodes, color, metric)
    sizes = _sizes(g, nodes, size, metric)
    shown = _shown_metrics(g, color, size, metric)
    lang, findings, notes, community_notes = _insights(g, nodes, metric, legend, color, lang, label,
                                                       insights)
    group_of, groups, group_title = _overview_groups(g, color, legend, metric, lang)
    group_notes = notes if legend and legend["kind"] == "category" else community_notes
    index = {n: i for i, n in enumerate(nodes)}
    grp = [group_of[n] for n in nodes]
    xs, ys, gx, gy = _seed_positions(grp, len(groups))

    palette = list(dict.fromkeys(colors))
    color_index = {c: i for i, c in enumerate(palette)}
    cat_index = {}
    if legend and legend["kind"] == "category":
        cat_index = {("" if it.get("missing") else it["label"]): i for i, it in enumerate(legend["items"])}

    columns = list(dict.fromkeys(k for n in nodes for k in g.nodes[n]))[:MAX_ATTR_COLUMNS]
    edge_width = _edge_width_attr(edge_width, triples)
    plain = [(u, v, d) for u, v, d in triples if u != v]  # sigma draws no self-loops
    widths = _scale([_number(d.get(edge_width)) if edge_width else None for _, _, d in plain],
                    0.5, 4.0, None) if edge_width else None
    flat = []
    for u, v, _ in plain:
        flat.append(index[u])
        flat.append(index[v])

    shown_counts = [0] * len(groups)
    for gi in grp:
        shown_counts[gi] += 1
    sizes_g = [grp_["size"] for grp_ in groups]
    gedges, gweights = _group_edges(g, group_of)

    return {
        "config": _localize(_config(g, nodes, triples, title, theme, legend, size, renderer="webgl",
                          groupTitle=group_title, lang=lang, insights=findings,
                          start="overview" if (len(nodes) > OVERVIEW_START[0]
                                               or len(plain) > OVERVIEW_START[1]) else "nodes",
                          groupName=i18n.metric_name(group_title, lang)), lang),
        "nodes": {
            "label": [_label(n, g.nodes[n], label) for n in nodes],
            "colors": palette,
            "c": [color_index[c] for c in colors],
            "size": sizes,
            "x": xs,
            "y": ys,
            "cat": [cat_index.get(k, -1) if k is not None else -1 for k in cats],
            "grp": grp,
            "metrics": {i18n.metric_name(k, lang): [_compact(v[n]) for n in nodes] for k, v in shown.items()},
            "attrs": {c: [g.nodes[n].get(c) for n in nodes] for c in columns},
        },
        "edges": {"e": flat, "w": widths},
        "groups": {
            "label": [grp_["label"] for grp_ in groups],
            "key": [grp_.get("key") for grp_ in groups],
            "note": [group_notes.get(grp_.get("key")) for grp_ in groups],
            "color": [grp_["color"] for grp_ in groups],
            "size": sizes_g,
            "shown": shown_counts,
            "x": gx,
            "y": gy,
            "e": gedges,
            "w": gweights,
        },
    }


def _insights(g, nodes, metric, legend, color, lang, label, enabled):
    """``(lang, findings, legend notes, community notes)`` for the view."""
    lang = i18n.get_language(lang)
    if not enabled or not len(g):
        return lang, [], {}, {}
    from ..insights import explain, profile
    communities = None
    rank = None
    if g.edge_count:
        by_label = {}
        for node, c in metric("community").items():
            by_label.setdefault(c, set()).add(node)
        communities = [by_label[k] for k in sorted(by_label)]
        rank = metric("pagerank")
    exp = explain(g, lang=lang, label=label, communities=communities, pagerank=rank)
    index = {n: i for i, n in enumerate(nodes)}
    findings = [{"kind": f.kind, "text": f.text, "group": f.group,
                 "nodes": [index[x] for x in f.nodes if x in index][:2000]}
                for f in exp.findings]
    community_notes = {p.label: p.traits[0].short(lang) for p in exp.profiles if p.traits}
    notes = {}
    if legend and legend["kind"] == "category":
        if color == "community":
            notes = community_notes
        elif isinstance(color, str) and color not in METRICS:
            by_value = profile(g, groups=color, lang=lang, label=label, pagerank=rank)
            notes = {p.label: p.traits[0].short(lang) for p in by_value if p.traits}
        for item in legend["items"]:
            if not item.get("missing") and item["label"] in notes:
                item["note"] = notes[item["label"]]
    return lang, findings, notes, community_notes


def _localize(config, lang):
    """Show built-in metric names in the page language; keep the raw name for the code."""
    legend = config.get("legend")
    if legend and isinstance(legend.get("title"), str):
        legend["metric"] = legend["title"]
        legend["title"] = i18n.metric_name(legend["title"], lang)
    if config.get("size"):
        config["size"] = i18n.metric_name(config["size"], lang)
    return config


def _compact(value):
    if isinstance(value, float):
        return float(f"{value:.5g}")
    return value


def _overview_groups(g, color, legend, metric, lang="en"):
    """One group per category (or community) over the whole graph, biggest first."""
    every = list(g)
    if legend and legend["kind"] == "category":
        values, _ = _values(g, every, color, metric)
        keys = ["" if v is None else _category_key(v) for v in values]
        palette = {("" if it.get("missing") else it["label"]): it["color"] for it in legend["items"]}
        title = legend.get("title") or "group"
    else:
        values = metric("community")
        keys = [str(values[n]) for n in every]
        palette = {}
        title = "community"
    counts = {}
    for k in keys:
        counts[k] = counts.get(k, 0) + 1
    if title in GROUP_METRICS:
        order = sorted(counts, key=lambda k: (-counts[k], int(k)))
    else:
        order = sorted(counts, key=lambda k: -counts[k])
    top = order[:MAX_GROUPS]
    groups = []
    slot = {}
    for i, k in enumerate(top):
        slot[k] = i
        if title == "community":
            name = f"{i18n.text(lang, 'group')} {k}"  # same words as explain()
        elif title in GROUP_METRICS:
            name = f"{i18n.metric_name(title, lang).capitalize()} {k}"
        else:
            name = k if k else "none"
        groups.append({"label": name, "key": k, "color": palette.get(k) or _category_color(i),
                       "size": counts[k]})
    if len(order) > len(top):
        rest = len(groups)
        groups.append({"label": i18n.text(lang, "smaller_groups", k=i18n.number(len(order) - len(top), lang)),
                       "color": MISSING_COLOR,
                       "size": sum(counts[k] for k in order[len(top):])})
        for k in order[len(top):]:
            slot[k] = rest
    return {n: slot[k] for n, k in zip(every, keys)}, groups, title


def _group_edges(g, group_of):
    weights = {}
    for u, v, d in g._edge_triples():
        a, b = group_of[u], group_of[v]
        if a == b:
            continue
        key = (a, b) if a < b else (b, a)
        w = _number(d.get("weight"))
        weights[key] = weights.get(key, 0.0) + (w if w is not None and w > 0 else 1.0)
    flat, ws = [], []
    for (a, b), w in weights.items():
        flat.append(a)
        flat.append(b)
        ws.append(round(w, 3))
    return flat, ws


def _seed_positions(grp, group_count, spacing=14.0, seed=7):
    """Start each group as a disc of its own, discs laid on a spiral, biggest in the middle.

    The layout engine refines this in the browser; starting from groups makes
    it settle much faster than starting from noise.
    """
    rng = random.Random(seed)
    members = [[] for _ in range(group_count)]
    for i, gi in enumerate(grp):
        members[gi].append(i)
    xs = [0.0] * len(grp)
    ys = [0.0] * len(grp)
    gx = [0.0] * group_count
    gy = [0.0] * group_count
    placed = 0
    for rank, gi in enumerate(sorted(range(group_count), key=lambda j: -len(members[j]))):
        k = max(1, len(members[gi]))
        radius = spacing * math.sqrt(k)
        if rank:
            dist = spacing * math.sqrt(placed) + radius
            angle = rank * 2.399963
            cx, cy = dist * math.cos(angle), dist * math.sin(angle)
        else:
            cx = cy = 0.0
        placed += k
        gx[gi], gy[gi] = round(cx, 1), round(cy, 1)
        for i in members[gi]:
            r = radius * math.sqrt(rng.random())
            a = 2 * math.pi * rng.random()
            xs[i] = round(cx + r * math.cos(a), 1)
            ys[i] = round(cy + r * math.sin(a), 1)
    return xs, ys, gx, gy


# --------------------------------------------------------------------- styling

def _values(g, nodes, spec, metric):
    """``(values, title)`` for a color/size spec, or ``(None, None)``."""
    if spec is None:
        return None, None
    if isinstance(spec, str):
        if spec in METRICS:
            values = metric(spec)
            return [values[n] for n in nodes], spec
        return [g.nodes[n].get(spec) for n in nodes], spec
    if isinstance(spec, dict):
        return [spec.get(n) for n in nodes], None
    if callable(spec):
        return [spec(n) for n in nodes], getattr(spec, "__name__", None)
    raise TarecoError(f"cannot use {spec!r} for color/size")


def _is_css_color(spec):
    return isinstance(spec, str) and (spec.startswith("#") or spec.startswith("rgb") or spec.startswith("hsl"))


def _colors(g, nodes, spec, metric):
    n = len(nodes)
    if spec is None or _is_css_color(spec):
        return [spec or PALETTE[0]] * n, [None] * n, None
    values, title = _values(g, nodes, spec, metric)
    present = [v for v in values if v is not None]
    numeric = present and all(_number(v) is not None for v in present)
    categorical = (not numeric or spec in GROUP_METRICS
                   or (all(isinstance(v, int) for v in present) and len(set(present)) <= len(PALETTE)
                       and spec not in METRICS))
    if not categorical:
        nums = [_number(v) for v in values]
        lo, hi = min(x for x in nums if x is not None), max(x for x in nums if x is not None)
        colors = [MISSING_COLOR if x is None else _gradient((x - lo) / (hi - lo) if hi > lo else 0.5)
                  for x in nums]
        legend = {"kind": "scale", "title": title, "min": lo, "max": hi, "colors": GRADIENT}
        return colors, [None] * n, legend

    counts = {}
    for v in present:
        key = _category_key(v)
        counts[key] = counts.get(key, 0) + 1
    if spec in GROUP_METRICS:
        order = sorted(counts, key=int)
    else:
        order = sorted(counts, key=lambda k: -counts[k])
    palette = {k: _category_color(i) for i, k in enumerate(order)}
    colors = [MISSING_COLOR if v is None else palette[_category_key(v)] for v in values]
    groups = [None if v is None else _category_key(v) for v in values]
    items = [{"label": k, "color": palette[k], "count": counts[k]} for k in order]
    missing = n - len(present)
    if missing:
        items.append({"label": "", "color": MISSING_COLOR, "count": missing, "missing": True})
        groups = [g_ if g_ is not None else "" for g_ in groups]
    return colors, groups, {"kind": "category", "title": title, "items": items}


def _category_key(value):
    if isinstance(value, (list, tuple, set, frozenset)):
        return ", ".join(str(v) for v in value)
    return str(value)


def _category_color(i):
    if i < len(PALETTE):
        return PALETTE[i]
    # golden-angle hues; hex because the WebGL renderer only reads hex/rgb colors
    r, g, b = colorsys.hls_to_rgb((i * 137.508) % 360 / 360, 0.58, 0.62)
    return f"#{round(r * 255):02x}{round(g * 255):02x}{round(b * 255):02x}"


def _gradient(t):
    t = min(1.0, max(0.0, t))
    pos = t * (len(GRADIENT) - 1)
    i = min(int(pos), len(GRADIENT) - 2)
    frac = pos - i
    a, b = _hex_rgb(GRADIENT[i]), _hex_rgb(GRADIENT[i + 1])
    r, g, bl = (round(x + (y - x) * frac) for x, y in zip(a, b))
    return f"#{r:02x}{g:02x}{bl:02x}"


def _hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _sizes(g, nodes, spec, metric):
    if spec is None:
        return [4.0] * len(nodes)
    if isinstance(spec, (int, float)) and not isinstance(spec, bool):
        return [float(spec)] * len(nodes)
    values, _ = _values(g, nodes, spec, metric)
    return _scale([_number(v) for v in values], 1.5, 18.0, 4.0)


def _number(value):
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value) if value == value else None
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "item"):
        return _number(value.item())
    return None


def _scale(values, lo_out, hi_out, default):
    present = [v for v in values if v is not None]
    if not present:
        return [default] * len(values)
    lo, hi = min(present), max(present)
    if hi == lo:
        return [default] * len(values)
    return [default if v is None else round(lo_out + (v - lo) / (hi - lo) * (hi_out - lo_out), 3)
            for v in values]

"""Interactive HTML view: a force-directed graph you can drag, search and explore."""

import html
import json
import os
import re
import sys
import tempfile
import webbrowser
from importlib import resources

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


def to_html(g, color=None, size=None, label=None, edge_width=None, title=None, dim=2,
            particles=False, theme="auto"):
    """The interactive view as a standalone HTML document (string).

    color       attribute name, a metric ("community", "pagerank", "degree",
                "betweenness", "closeness", "clustering", "core", "component"),
                a {node: value} dict, a function of the node, or one CSS color.
                Defaults to "community".
    size        same kinds of values (numbers); defaults to "pagerank".
    label       attribute holding the text shown for each node (default: the id).
    edge_width  edge attribute for line width (default: "weight" when present).
    dim         2 or 3. The 3D view loads its library from a CDN.
    particles   animated dots flowing along the edges.
    theme       "auto", "dark" or "light".
    """
    if dim not in (2, 3):
        raise TarecoError("dim must be 2 or 3")
    payload = build_payload(g, color=color, size=size, label=label, edge_width=edge_width,
                            title=title, dim=dim, particles=particles, theme=theme)
    data = json.dumps(payload, default=json_default, ensure_ascii=False).replace("<", "\\u003c")
    if dim == 3:
        lib = f'<script src="{LIB_3D}"></script>'
    else:
        lib = "<script>" + _asset("force-graph.min.js") + "</script>"
    parts = {
        "__TITLE__": html.escape(payload["config"]["title"] or "tareco"),
        "<!--LIB-->": lib,
        "/*DATA*/": "window.__TARECO__ = " + data + ";",
        "/*STYLE*/": _asset("style.css"),
        "/*APP*/": _asset("app.js"),
    }
    # one pass, so inserted text is never scanned for markers again
    return re.sub("|".join(re.escape(k) for k in parts), lambda m: parts[m.group(0)],
                  _asset("template.html"))


def save(g, path, **options):
    """Write the view to ``path`` and return the absolute path."""
    with open(path, "w", encoding="utf-8") as f:
        f.write(to_html(g, **options))
    return os.path.abspath(path)


def notebook_html(g, height=560, **options):
    doc = html.escape(to_html(g, **options), quote=True)
    return (f'<iframe srcdoc="{doc}" style="width:100%;height:{int(height)}px;border:0;'
            f'border-radius:12px" sandbox="allow-scripts allow-downloads"></iframe>')


def show(g, height=560, **options):
    """Inline in Jupyter/VS Code/Colab; otherwise opens the default browser."""
    if _in_notebook():
        from IPython.display import HTML, display
        display(HTML(notebook_html(g, height=height, **options)))
        return
    folder = os.path.join(tempfile.gettempdir(), "tareco")
    os.makedirs(folder, exist_ok=True)
    fd, path = tempfile.mkstemp(suffix=".html", prefix="graph-", dir=folder)
    os.close(fd)
    save(g, path, **options)
    webbrowser.open("file://" + os.path.abspath(path).replace(os.sep, "/"))


def _in_notebook():
    ipython = sys.modules.get("IPython")
    if ipython is None:
        return False
    try:
        shell = ipython.get_ipython()
    except Exception:
        return False
    return shell is not None and getattr(shell, "kernel", None) is not None


def _asset(name):
    return resources.files(__name__).joinpath(name).read_text(encoding="utf-8")


# --------------------------------------------------------------------- payload

def build_payload(g, color=None, size=None, label=None, edge_width=None, title=None, dim=2,
                  particles=False, theme="auto"):
    nodes = list(g)
    cache = {}

    def metric(name):
        if name not in cache:
            cache[name] = _compute_metric(g, name)
        return cache[name]

    if color is None:
        color = "community" if g.edge_count else None
    if size is None:
        size = "pagerank" if g.edge_count else None

    shown_metrics = {"degree": g.degree()}
    if g.directed:
        shown_metrics = {"in": g.in_degree(), "out": g.out_degree()}

    colors, groups, legend = _colors(g, nodes, color, metric)
    sizes = _sizes(g, nodes, size, metric)
    for name in (color, size):
        if isinstance(name, str) and name in METRICS:
            shown_metrics[name] = metric(name)

    if edge_width is None and any(isinstance(d.get("weight"), (int, float)) for _, _, d in g._edge_triples()):
        edge_width = "weight"
    triples = list(g._edge_triples())
    widths = _scale([_number(d.get(edge_width)) if edge_width else None for _, _, d in triples], 0.6, 5.0, 1.0)

    index = {n: i for i, n in enumerate(nodes)}
    out_nodes = []
    for i, n in enumerate(nodes):
        attrs = g.nodes[n]
        text = attrs.get(label) if label is not None else None
        out_nodes.append({
            "id": i,
            "label": str(n if text is None else text),
            "color": colors[i],
            "val": sizes[i],
            "group": groups[i],
            "attrs": attrs,
            "metrics": {k: v[n] for k, v in shown_metrics.items()},
        })
    out_links = []
    for (u, v, d), w in zip(triples, widths):
        curve = 0.0
        if u == v:
            curve = 0.6
        elif g.directed and g.has_edge(v, u):
            curve = 0.18
        out_links.append({"source": index[u], "target": index[v], "w": w, "curve": curve, "attrs": d})

    return {
        "config": {
            "title": title if title is not None else g.attrs.get("title", ""),
            "directed": g.directed,
            "dim": dim,
            "particles": bool(particles),
            "theme": theme,
            "legend": legend,
            "size": size if isinstance(size, str) else None,
            "counts": {"nodes": len(nodes), "edges": g.edge_count},
        },
        "nodes": out_nodes,
        "links": out_links,
    }


def _compute_metric(g, name):
    if name == "pagerank":
        return g.pagerank()
    if name == "degree":
        return g.degree()
    if name == "betweenness":
        return g.betweenness()
    if name == "closeness":
        return g.closeness()
    if name == "clustering":
        return g.clustering()
    if name == "core":
        return g.core_number()
    groups = g.communities() if name == "community" else g.components()
    return {n: i + 1 for i, members in enumerate(groups) for n in members}


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
        lo, hi = min(present), max(present)
        colors = [MISSING_COLOR if v is None else _gradient((v - lo) / (hi - lo) if hi > lo else 0.5)
                  for v in values]
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
    hue = (i * 137.508) % 360
    return f"hsl({hue:.0f}, 62%, 58%)"


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

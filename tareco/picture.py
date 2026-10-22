"""A still picture of the graph, made in Python: SVG with nothing else installed, PNG with Pillow.

For slides, e-mails and reports that cannot hold an interactive page. The
layout is a force-directed one computed here (nodes start next to their group),
so the same graph always gives the same picture.
"""

import html
import math
import random

from .errors import TarecoError

LIGHT = {"bg": "#ffffff", "text": "#0f172a", "muted": "#64748b", "edge": "#94a3b8", "halo": "#ffffff"}
DARK = {"bg": "#0b1020", "text": "#e2e8f0", "muted": "#94a3b8", "edge": "#64748b", "halo": "#0b1020"}
FONT = "ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, sans-serif"


def layout(n, edges, groups=None, iterations=150, seed=7):
    """Positions for ``n`` nodes and ``edges`` as ``(i, j, strength)``: Fruchterman-Reingold on a grid."""
    from .viz import _seed_positions
    if n == 0:
        return [], []
    if groups is None:
        groups = [0] * n
    count = max(groups) + 1
    xs, ys, _, _ = _seed_positions(groups, count, spacing=1.0, seed=seed)
    rng = random.Random(seed)
    xs = [x + rng.uniform(-0.01, 0.01) for x in xs]
    ys = [y + rng.uniform(-0.01, 0.01) for y in ys]
    k, cell = 1.0, 2.0
    temp = max(1.0, math.sqrt(n) * 0.1)
    cool = temp / (iterations + 1)
    for _ in range(iterations):
        dx, dy = [0.0] * n, [0.0] * n
        grid = {}
        for i in range(n):
            grid.setdefault((int(xs[i] // cell), int(ys[i] // cell)), []).append(i)
        for (cx, cy), members in grid.items():
            near = [j for ox in (-1, 0, 1) for oy in (-1, 0, 1) for j in grid.get((cx + ox, cy + oy), ())]
            for i in members:
                xi, yi = xs[i], ys[i]
                for j in near:
                    if j <= i:
                        continue
                    ddx, ddy = xi - xs[j], yi - ys[j]
                    d2 = ddx * ddx + ddy * ddy
                    if d2 >= cell * cell:
                        continue
                    d = math.sqrt(d2) or 0.01
                    f = k * k / d / d
                    dx[i] += ddx * f
                    dy[i] += ddy * f
                    dx[j] -= ddx * f
                    dy[j] -= ddy * f
        for i, j, w in edges:
            ddx, ddy = xs[i] - xs[j], ys[i] - ys[j]
            d = math.sqrt(ddx * ddx + ddy * ddy) or 0.01
            f = d / k * w
            dx[i] -= ddx * f
            dy[i] -= ddy * f
            dx[j] += ddx * f
            dy[j] += ddy * f
        for i in range(n):
            dx[i] -= xs[i] * 0.02  # a little gravity keeps islands in the frame
            dy[i] -= ys[i] * 0.02
            d = math.sqrt(dx[i] * dx[i] + dy[i] * dy[i])
            if d > 0:
                step = min(d, temp)
                xs[i] += dx[i] / d * step
                ys[i] += dy[i] / d * step
        temp = max(0.02, temp - cool)
    return xs, ys


class _Scene:
    """Everything to draw, in pixels: edges, nodes, labels, legend and title."""

    def __init__(self, g, color=None, size=None, label=None, title=None, width=1200, height=800,
                 theme="light", max_nodes=1000, labels=20, edge_width=None, iterations=150):
        from .viz import (_colors, _defaults, _edge_width_attr, _label, _metric_cache, _number, _reduce,
                          _scale, _sizes)
        if theme not in ("light", "dark"):
            raise TarecoError('theme must be "light" or "dark"')
        self.palette = LIGHT if theme == "light" else DARK
        self.width, self.height = width, height
        self.title = title if title is not None else g.attrs.get("title", "")
        self.directed = g.directed
        metric = _metric_cache(g)
        nodes, triples = _reduce(g, max_nodes, max_nodes * 4, metric)
        color, size = _defaults(g, color, size)
        self.colors, groups, self.legend = _colors(g, nodes, color, metric)
        sizes = _sizes(g, nodes, size, metric)
        self.radius = [2.5 + math.sqrt(s) * 1.6 for s in sizes]
        self.names = [_label(n, g.nodes[n], label) for n in nodes]
        index = {n: i for i, n in enumerate(nodes)}
        width_attr = _edge_width_attr(g, edge_width, triples)
        widths = _scale([_number(d.get(width_attr)) if width_attr else None for _, _, d in triples],
                        0.6, 3.5, 0.9)
        pairs = [(index[u], index[v], w) for (u, v, _), w in zip(triples, widths) if u != v]
        keys = sorted({x for x in groups if x is not None}, key=str)
        slot = {x: i for i, x in enumerate(keys)}
        xs, ys = layout(len(nodes), [(i, j, 0.5 + 0.5 * w / 3.5) for i, j, w in pairs],
                        [slot.get(x, 0) if x is not None else 0 for x in groups], iterations=iterations)
        top = 56 if self.title else 24
        pad = 28
        if xs:
            x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
            span = max(x1 - x0, y1 - y0, 1e-9)
            scale = min((width - 2 * pad) / max(x1 - x0, span * 0.2), (height - top - pad) / max(y1 - y0, span * 0.2))
            ox = pad + (width - 2 * pad - (x1 - x0) * scale) / 2
            oy = top + (height - top - pad - (y1 - y0) * scale) / 2
            self.x = [ox + (x - x0) * scale for x in xs]
            self.y = [oy + (y - y0) * scale for y in ys]
        else:
            self.x, self.y = [], []
        self.edges = pairs
        self.edge_alpha = max(0.08, min(0.55, 6 / math.sqrt(max(1, len(pairs)))))
        order = sorted(range(len(nodes)), key=lambda i: -self.radius[i])
        self.labelled = set()
        boxes = []
        for i in order:  # the biggest first; a name that would cover another is left out
            if len(self.labelled) >= labels:
                break
            w = 6.8 * len(self.names[i]) + 4
            box = (self.x[i] - w / 2, self.y[i] + self.radius[i] + 2, self.x[i] + w / 2,
                   self.y[i] + self.radius[i] + 17)
            if any(box[0] < b[2] and b[0] < box[2] and box[1] < b[3] and b[1] < box[3] for b in boxes):
                continue
            boxes.append(box)
            self.labelled.add(i)
        self.order = order[::-1]  # small first, so big nodes sit on top


def to_svg(g, **options):
    """The picture as SVG text. Same options as ``save``."""
    s = _Scene(g, **options)
    p = s.palette
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{s.width}" height="{s.height}" '
           f'viewBox="0 0 {s.width} {s.height}" font-family="{FONT}">',
           f'<rect width="100%" height="100%" fill="{p["bg"]}"/>']
    if s.directed and len(s.edges) <= 3000:
        out.append(f'<defs><marker id="arrow" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="6" '
                   f'markerHeight="6" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{p["edge"]}"/>'
                   f'</marker></defs>')
        arrow = ' marker-end="url(#arrow)"'
    else:
        arrow = ""
    out.append(f'<g stroke="{p["edge"]}" stroke-opacity="{s.edge_alpha:.2f}" stroke-linecap="round">')
    for i, j, w in s.edges:
        x1, y1, x2, y2 = s.x[i], s.y[i], s.x[j], s.y[j]
        if arrow:  # stop at the rim of the target
            d = math.hypot(x2 - x1, y2 - y1) or 1
            x2 -= (x2 - x1) / d * s.radius[j]
            y2 -= (y2 - y1) / d * s.radius[j]
        out.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke-width="{w:.2f}"{arrow}/>')
    out.append("</g>")
    out.append(f'<g stroke="{p["bg"]}" stroke-width="1">')
    for i in s.order:
        out.append(f'<circle cx="{s.x[i]:.1f}" cy="{s.y[i]:.1f}" r="{s.radius[i]:.1f}" fill="{s.colors[i]}"/>')
    out.append("</g>")
    out.append(f'<g font-size="12" font-weight="500" fill="{p["text"]}" text-anchor="middle" '
               f'stroke="{p["halo"]}" stroke-width="3" paint-order="stroke" stroke-linejoin="round">')
    for i in sorted(s.labelled):
        out.append(f'<text x="{s.x[i]:.1f}" y="{s.y[i] + s.radius[i] + 13:.1f}">{html.escape(s.names[i])}</text>')
    out.append("</g>")
    if s.title:
        out.append(f'<text x="24" y="36" font-size="20" font-weight="650" fill="{p["text"]}">'
                   f'{html.escape(str(s.title))}</text>')
    out += _svg_legend(s)
    out.append("</svg>")
    return "\n".join(out)


def _legend_items(s):
    legend = s.legend
    if not legend or legend.get("kind") != "category":
        return None, []
    items = [it for it in legend["items"] if not it.get("missing")][:8]
    return legend.get("title"), items


def _svg_legend(s):
    title, items = _legend_items(s)
    if not items:
        return []
    p = s.palette
    y = s.height - 20 - 18 * len(items) - (18 if title else 0)
    out = [f'<g font-size="12" fill="{p["text"]}">']
    if title:
        out.append(f'<text x="24" y="{y:.0f}" fill="{p["muted"]}" font-weight="600">{html.escape(str(title))}</text>')
        y += 18
    for it in items:
        out.append(f'<circle cx="30" cy="{y - 4:.0f}" r="5" fill="{it["color"]}"/>'
                   f'<text x="42" y="{y:.0f}">{html.escape(str(it["label"]))}</text>')
        y += 18
    out.append("</g>")
    return out


def to_png(g, path, **options):
    """Write the picture as PNG (needs Pillow: pip install pillow)."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        raise TarecoError("PNG pictures need Pillow (pip install pillow); .svg works without it") from None
    s = _Scene(g, **options)
    k = 2  # draw twice as big and shrink: smooth edges without anti-aliasing tricks
    p = s.palette
    base = Image.new("RGBA", (s.width * k, s.height * k), p["bg"])
    lines = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(lines)
    edge = _rgb(p["edge"]) + (int(255 * s.edge_alpha),)
    for i, j, w in s.edges:
        draw.line([(s.x[i] * k, s.y[i] * k), (s.x[j] * k, s.y[j] * k)], fill=edge, width=max(1, round(w * k)))
    base = Image.alpha_composite(base, lines)
    draw = ImageDraw.Draw(base)
    ring = _rgb(p["bg"])
    for i in s.order:
        r = s.radius[i] * k
        draw.ellipse([s.x[i] * k - r, s.y[i] * k - r, s.x[i] * k + r, s.y[i] * k + r],
                     fill=_rgb(s.colors[i]), outline=ring, width=k)
    font = _font(ImageFont, 12 * k)
    for i in sorted(s.labelled):
        draw.text((s.x[i] * k, (s.y[i] + s.radius[i] + 9) * k), s.names[i], font=font, fill=_rgb(p["text"]),
                  anchor="mt", stroke_width=2 * k, stroke_fill=_rgb(p["halo"]))
    if s.title:
        draw.text((24 * k, 22 * k), str(s.title), font=_font(ImageFont, 20 * k), fill=_rgb(p["text"]))
    title, items = _legend_items(s)
    if items:
        y = s.height - 20 - 18 * len(items) - (18 if title else 0)
        if title:
            draw.text((24 * k, (y - 12) * k), str(title), font=font, fill=_rgb(p["muted"]))
            y += 18
        for it in items:
            draw.ellipse([25 * k, (y - 9) * k, 35 * k, (y + 1) * k], fill=_rgb(it["color"]))
            draw.text((42 * k, (y - 12) * k), str(it["label"]), font=font, fill=_rgb(p["text"]))
            y += 18
    base.resize((s.width, s.height), Image.LANCZOS).convert("RGB").save(path)


FONT_FILES = ("segoeui.ttf", "arial.ttf", "Arial.ttf", "DejaVuSans.ttf", "LiberationSans-Regular.ttf",
              "Helvetica.ttc", "/System/Library/Fonts/Helvetica.ttc",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")


def _font(ImageFont, size):
    """A system font with accents (São Paulo); Pillow's own default as the last resort."""
    for name in FONT_FILES:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # Pillow before 10.1 has one small default font
        return ImageFont.load_default()


def _rgb(color):
    color = color.lstrip("#")
    if len(color) == 3:
        color = "".join(c * 2 for c in color)
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))

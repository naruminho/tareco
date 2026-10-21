"""Networks that change over time: snapshots per period, what changed, and how far things spread."""

import datetime as dt
import math
import re
from collections import Counter

from . import i18n
from .errors import TarecoError
from .graph import Graph
from .insights import Explanation, Finding, _median
from .io import (MAX_ROWS, SOURCE_COLUMNS, TARGET_COLUMNS, _add_nodes_from, _missing, _pick_column,
                 _resolve, iter_table)

FREQS = ("day", "week", "month", "quarter", "year")
MAX_AUTO_PERIODS = 24  # "auto" picks the finest unit that gives at most this many periods
NUMBER_BINS = 20
DMY = re.compile(r"^\s*(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})(?:[ T](\d{1,2}):(\d{2})(?::(\d{2}))?)?\s*$")
YMD = re.compile(r"^\s*(\d{4})[/.](\d{1,2})[/.](\d{1,2})(?:[ T](\d{1,2}):(\d{2})(?::(\d{2}))?)?\s*$")


def timeline(data, time, freq="auto", source=None, target=None, directed=False, weight=None,
             nodes=None, cumulative=False, dayfirst=None, max_rows=MAX_ROWS):
    """A network that changes over time, built from a table of timed events.

    data        CSV path, pandas/polars/Spark DataFrame or rows; one row per event.
    time        the column with when it happened: dates, datetimes, ISO text,
                dd/mm/yyyy or mm/dd/yyyy text, or plain numbers (steps, years).
    freq        "day", "week", "month", "quarter", "year", a number (bin size
                for numeric times) or "auto" (a sensible number of periods).
    weight      column to add up per connection (default: count events).
    nodes       node attributes, like ``Graph(nodes=...)``.
    cumulative  each snapshot holds everything up to its period.
    dayfirst    for slash dates: True for dd/mm, False for mm/dd, None to infer.
    """
    columns, rows = iter_table(data, max_rows)
    if not columns:
        raise TarecoError("the table is empty")
    if time not in columns:
        raise TarecoError(f"no column {time!r} for time; columns are {columns}")
    rest = [c for c in columns if c != time]
    s = _pick_column(rest, source, SOURCE_COLUMNS, "source")
    t = _pick_column(rest, target, TARGET_COLUMNS, "target", exclude=s)
    raw = []
    for row in rows:
        u, v, when = row.get(s), row.get(t), row.get(time)
        if _missing(u) or _missing(v) or _missing(when):
            continue
        w = row.get(weight) if weight else 1
        if not isinstance(w, (int, float)) or isinstance(w, bool) or w != w:
            w = 1 if not weight else 0
        raw.append((when, u, v, float(w) if isinstance(w, float) else w))
    if not raw:
        raise TarecoError("no rows with source, target and time")
    times = _parse_times([r[0] for r in raw], dayfirst)
    events = sorted(((tm, u, v, w) for tm, (_, u, v, w) in zip(times, raw)), key=lambda e: e[0])
    return Timeline(events, freq, directed, cumulative, nodes)


class Timeline:
    """Snapshots of a network over time. Index it by period label or position."""

    def __init__(self, events, freq, directed, cumulative, nodes=None):
        self.events = events
        self.directed = directed
        self.cumulative = cumulative
        numeric = isinstance(events[0][0], (int, float))
        if numeric:
            self.freq, keyer, keys, labels = _numeric_periods([e[0] for e in events], freq)
        else:
            if freq == "auto":
                freq = _auto_freq(events[0][0], events[-1][0])
            if freq not in FREQS:
                raise TarecoError(f"freq must be one of {FREQS}, a number or 'auto'")
            self.freq = freq
            keys = _span(_key(events[0][0], freq), _key(events[-1][0], freq), freq)
            labels = [_label(k, freq) for k in keys]
            keyer = lambda tm: _key(tm, freq)  # noqa: E731
        position = {k: i for i, k in enumerate(keys)}
        self.periods = labels
        self.period_of = [position[keyer(e[0])] for e in events]
        self._nodes_table = _resolve(nodes) if nodes is not None else None
        self.graphs = self._snapshots()
        self.union = self._union()

    # ------------------------------------------------------------- building

    def _new_graph(self):
        g = Graph(directed=self.directed)
        if self._nodes_table is not None:
            _add_nodes_from(g, self._nodes_table, None)
        return g

    def _snapshots(self):
        per = [dict() for _ in self.periods]
        for (tm, u, v, w), p in zip(self.events, self.period_of):
            key = (u, v) if self.directed or (v, u) not in per[p] else (v, u)
            entry = per[p].setdefault(key, [0, 0])
            entry[0] += w
            entry[1] += 1
        graphs = []
        running = {}
        for p, edges in enumerate(per):
            if self.cumulative:
                for key, (w, c) in edges.items():
                    if not self.directed and key not in running and key[::-1] in running:
                        key = key[::-1]
                    entry = running.setdefault(key, [0, 0])
                    entry[0] += w
                    entry[1] += c
                edges = running
            g = Graph(directed=self.directed)
            for (u, v), (w, c) in edges.items():
                g._add_edge(u, v, {"weight": w, "count": c})
            g.attrs["period"] = self.periods[p]
            graphs.append(g)
        return graphs

    def _union(self):
        g = self._new_graph()
        for (tm, u, v, w), p in zip(self.events, self.period_of):
            if g.has_edge(u, v):
                d = g.edges[u, v]
                d["weight"] += w
                d["count"] += 1
                if d["periods"][-1] != p:
                    d["periods"].append(p)
                d["last"] = self.periods[p]
            else:
                g._add_edge(u, v, {"weight": w, "count": 1, "first": self.periods[p],
                                   "last": self.periods[p], "periods": [p]})
        g.attrs.update({"time": self.freq, "periods": list(self.periods)})
        return g

    # ------------------------------------------------------------- access

    def __len__(self):
        return len(self.periods)

    def __iter__(self):
        return iter(zip(self.periods, self.graphs))

    def __getitem__(self, key):
        if isinstance(key, int):
            return self.graphs[key]
        try:
            return self.graphs[self.periods.index(str(key))]
        except ValueError:
            raise TarecoError(f"no period {key!r}; periods are {self.periods}") from None

    def __repr__(self):
        return (f"<Timeline by {self.freq}, {len(self.periods)} periods, "
                f"{len(self.union)} nodes, {self.union.edge_count} connections>")

    def activity(self):
        """Per period: active nodes, connections and total weight."""
        out = []
        for label, g in zip(self.periods, self._own_graphs()):
            total = sum(d["weight"] for _, _, d in g._edge_triples())
            out.append({"period": label, "nodes": sum(1 for x in g if g.degree(x)),
                        "connections": g.edge_count, "weight": total})
        return out

    def _own_graphs(self):
        """Per-period snapshots even when the timeline is cumulative."""
        if not self.cumulative:
            return self.graphs
        flat = Timeline.__new__(Timeline)
        flat.__dict__.update(self.__dict__)
        flat.cumulative = False
        return flat._snapshots()

    # ------------------------------------------------------------ insights

    def changes(self, lang=None, label=None, limit=12):
        """What changed from one period to the next, in plain language."""
        lang = i18n.get_language(lang)
        T = lambda key, **kw: i18n.text(lang, key, **kw)  # noqa: E731
        num = lambda v: i18n.number(v, lang)  # noqa: E731
        name = lambda x: _name(self.union, x, label)  # noqa: E731
        graphs = self._own_graphs()
        P = len(graphs)
        degrees = [{x: len(set(g._all_neighbors(x)) - {x}) for x in g if g.degree(x)} for g in graphs]
        sizes = [g.edge_count for g in graphs]
        out = []

        moves = []
        for p in range(1, P):
            a, b = sizes[p - 1], sizes[p]
            if max(a, b) < 5:
                continue
            change = (b - a) / max(a, 1)
            if change >= 0.5 or change <= -1 / 3:
                key = "activity_up" if change > 0 else "activity_down"
                text = T(key, pct=i18n.percent(abs(change), lang), period=self.periods[p], a=num(a), b=num(b))
                moves.append((abs(math.log((b + 1) / (a + 1))), Finding(key, text, list(degrees[p]), period=p)))
        out += [f for _, f in sorted(moves, key=lambda m: -m[0])[:3]]

        seen = set()
        waves = []
        for p in range(P):
            active = set(degrees[p])
            new = active - seen
            if p and len(new) >= max(3, 0.1 * len(active)):
                waves.append((len(new), Finding("newcomers", T("newcomers", k=num(len(new)), period=self.periods[p]),
                                                sorted(new, key=lambda x: -degrees[p][x]), period=p)))
            seen |= active
        out += [f for _, f in sorted(waves, key=lambda w: -w[0])[:2]]

        history = Counter()
        jumps = []
        for p in range(P):
            deg = degrees[p]
            typical = _median(sorted(deg.values())) if deg else 0
            for x, d in (deg.items() if p else ()):
                before = history[x] / p
                if x in history:
                    # a jump counts when it beats both the node's past and the period's typical node
                    if d >= max(6, 3 * before + 3, 5 * typical):
                        text = T("surge", name=name(x), d=num(d), period=self.periods[p], avg=num(round(before, 1)))
                        jumps.append((d / max(1, before, typical), Finding("surge", text, [x] + _nbrs(graphs[p], x),
                                                                           period=p)))
                elif d >= max(5, 5 * typical):
                    text = T("debut", name=name(x), d=num(d), period=self.periods[p])
                    jumps.append((d / max(1, typical), Finding("debut", text, [x] + _nbrs(graphs[p], x), period=p)))
            history.update(deg)
        out += [f for _, f in sorted(jumps, key=lambda j: -j[0])[:5]]

        out += self._group_changes(graphs, degrees, lang, name)[:4]
        out.sort(key=lambda f: f.period)
        return out[:limit]

    def _group_changes(self, graphs, degrees, lang, name):
        def groups_of(g, deg):
            if g.edge_count < 5:
                return []
            return [c for c in g.communities() if len(c) >= 5]

        def around(c, deg):
            return sorted(c, key=lambda x: -deg.get(x, 0))[:3]

        out = []
        prev = None
        for p, g in enumerate(graphs):
            cur = groups_of(g, degrees[p])
            if prev is not None and cur:
                pdeg = degrees[p - 1]
                for c in cur:
                    best = max((len(c & q) / len(c | q) for q in prev), default=0)
                    parents = [q for q in prev if len(c & q) >= 0.3 * len(q)]
                    if len(parents) >= 2:
                        a, b = (around(q, pdeg)[0] for q in parents[:2])
                        out.append((len(c), Finding("merge", i18n.text(lang, "merge", period=self.periods[p],
                                                                        a=name(a), b=name(b)), sorted(c, key=str), period=p)))
                    elif best < 0.2:
                        names = i18n.join([name(x) for x in around(c, degrees[p])], lang)
                        out.append((len(c), Finding("new_group", i18n.text(lang, "new_group", k=i18n.number(len(c), lang),
                                                                            period=self.periods[p], names=names),
                                                    sorted(c, key=str), period=p)))
                active = set(degrees[p])
                for q in prev:
                    still = q & active
                    if len(still) < 5:
                        continue
                    children = [c for c in cur if len(c & still) >= 0.3 * len(still)]
                    if len(children) >= 2:
                        names = i18n.join([name(around(c, degrees[p])[0]) for c in children[:3]], lang)
                        out.append((len(q), Finding("split", i18n.text(lang, "split", period=self.periods[p],
                                                                        a=name(around(q, pdeg)[0]), names=names),
                                                    sorted(set().union(*children), key=str), period=p)))
            prev = cur if cur else prev
        return [f for _, f in sorted(out, key=lambda o: -o[0])]

    def explain(self, lang=None, label=None, limit=12):
        """The story of the network over time, then what holds for the whole period."""
        lang = i18n.get_language(lang)
        T = lambda key, **kw: i18n.text(lang, key, **kw)  # noqa: E731
        num = lambda v: i18n.number(v, lang)  # noqa: E731
        acts = self.activity()
        unit = i18n.text(lang, "unit_" + (self.freq if self.freq in FREQS else "period"))
        findings = [Finding("time_span", T("time_span", first=self.periods[0], last=self.periods[-1],
                                           k=num(len(self.periods)), unit=unit, n=num(len(self.union)),
                                           m=num(self.union.edge_count)))]
        busiest = max(range(len(acts)), key=lambda i: acts[i]["connections"])
        findings.append(Finding("busiest", T("busiest", period=self.periods[busiest],
                                             m=num(acts[busiest]["connections"])), period=busiest))
        quiet = sum(1 for a in acts if a["connections"] == 0)
        if quiet:
            findings.append(Finding("quiet", T("quiet", k=num(quiet))))
        findings += self.changes(lang=lang, label=label, limit=limit)
        whole = self.union.explain(lang=lang, label=label, weight="weight")
        keep = ("groups", "group", "central", "broker", "cycle", "pass_through", "fan_in", "fan_out")
        findings += [f for f in whole.findings if f.kind in keep]
        return Explanation(findings, whole.profiles, lang)

    def spread(self, start, since=None):
        """When each node could first have been reached from ``start``, following events in order.

        A path only counts if its events happen one after the other (A meets B,
        then B meets C). Returns ``{node: time}``, earliest first.
        """
        starts = list(start) if isinstance(start, (list, tuple, set, frozenset)) else [start]
        for x in starts:
            if x not in self.union:
                raise TarecoError(f"node {x!r} is not in the timeline")
        if since is not None:
            since = _parse_times([since], None)[0]
        first = since if since is not None else self.events[0][0]
        reached = {x: first for x in starts}
        for tm, u, v, _ in self.events:
            if since is not None and tm < since:
                continue
            if u in reached and v not in reached:
                reached[v] = tm
            elif not self.directed and v in reached and u not in reached:
                reached[u] = tm
        return dict(sorted(reached.items(), key=lambda kv: kv[1]))

    # ---------------------------------------------------------------- view

    def _time_info(self):
        acts = self.activity()
        return {"periods": list(self.periods), "cumulative": self.cumulative,
                "counts": [a["connections"] for a in acts]}

    def to_html(self, lang=None, label=None, **options):
        from .viz import to_html
        return to_html(self.union, time=self._time_info(), lang=lang, label=label,
                       insights=self.explain(lang=lang, label=label), **options)

    def report(self, path=None, title=None, lang=None, label=None, **view):
        """Like ``Graph.report``, plus activity per period and the time slider."""
        from .report import report
        return report(self.union, path, title=title, lang=lang, label=label, timeline=self, **view)

    def save(self, path, **options):
        import os
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_html(**options))
        return os.path.abspath(path)

    def show(self, lang=None, label=None, **options):
        """The union of all periods, with a time slider to replay it."""
        from .viz import show
        show(self.union, time=self._time_info(), lang=lang, label=label,
             insights=self.explain(lang=lang, label=label), **options)

    def _repr_html_(self):
        if len(self.union) > 200_000:
            return None
        from .viz import notebook_html
        return notebook_html(self.union, time=self._time_info(), insights=self.explain())


def _nbrs(g, x):
    return [y for y in g._all_neighbors(x) if y != x]


def _name(g, node, label):
    if label is not None and node in g:
        value = g.nodes[node].get(label)
        if value is not None:
            return str(value)
    return str(node)


# ------------------------------------------------------------------- parsing

def _parse_times(values, dayfirst):
    if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in values):
        return list(values)
    out = []
    slashed = []
    for v in values:
        parsed = _as_datetime(v)
        out.append(parsed)
        if parsed is None and isinstance(v, str) and DMY.match(v):
            slashed.append(v)
    if slashed:
        if dayfirst is None:
            dayfirst = _infer_dayfirst(slashed)
        for i, v in enumerate(values):
            if out[i] is None and isinstance(v, str):
                m = DMY.match(v)
                if m:
                    a, b, y, hh, mm, ss = m.groups()
                    day, month = (int(a), int(b)) if dayfirst else (int(b), int(a))
                    out[i] = dt.datetime(int(y), month, day, int(hh or 0), int(mm or 0), int(ss or 0))
    bad = [v for v, p in zip(values, out) if p is None]
    if bad:
        raise TarecoError(f"cannot read {bad[0]!r} as a time; use dates, ISO text (2026-03-01) "
                          f"or numbers")
    return out


def _as_datetime(v):
    if isinstance(v, dt.datetime):
        if hasattr(v, "to_pydatetime"):  # pandas Timestamp
            v = v.to_pydatetime()
        if v.tzinfo is not None:
            v = v.astimezone(dt.timezone.utc).replace(tzinfo=None)
        return v
    if isinstance(v, dt.date):
        return dt.datetime(v.year, v.month, v.day)
    if not isinstance(v, str):
        return None
    text = v.strip()
    if text.endswith("Z"):
        text = text[:-1]
    try:
        parsed = dt.datetime.fromisoformat(text)
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(dt.timezone.utc).replace(tzinfo=None)
        return parsed
    except ValueError:
        pass
    m = YMD.match(text)
    if m:
        y, mo, d, hh, mm, ss = m.groups()
        return dt.datetime(int(y), int(mo), int(d), int(hh or 0), int(mm or 0), int(ss or 0))
    return None


def _infer_dayfirst(texts):
    first_big = second_big = False
    for v in texts:
        a, b = (int(x) for x in DMY.match(v).groups()[:2])
        first_big |= a > 12
        second_big |= b > 12
    if first_big and not second_big:
        return True
    if second_big and not first_big:
        return False
    raise TarecoError("dates like 03/04/2026 are ambiguous here; pass dayfirst=True (dd/mm) or False (mm/dd)")


def _key(t, freq):
    if freq == "day":
        return t.date()
    if freq == "week":
        d = t.date()
        return d - dt.timedelta(days=d.weekday())
    if freq == "month":
        return (t.year, t.month)
    if freq == "quarter":
        return (t.year, (t.month - 1) // 3 + 1)
    return t.year


def _next(k, freq):
    if freq == "day":
        return k + dt.timedelta(days=1)
    if freq == "week":
        return k + dt.timedelta(days=7)
    if freq == "month":
        return (k[0] + k[1] // 12, k[1] % 12 + 1)
    if freq == "quarter":
        return (k[0] + k[1] // 4, k[1] % 4 + 1)
    return k + 1


def _span(first, last, freq, cap=None):
    keys = [first]
    while keys[-1] != last:
        keys.append(_next(keys[-1], freq))
        if cap is not None and len(keys) > cap:
            break
    return keys


def _label(k, freq):
    if freq in ("day", "week"):
        return k.isoformat()
    if freq == "month":
        return f"{k[0]}-{k[1]:02d}"
    if freq == "quarter":
        return f"{k[0]}-Q{k[1]}"
    return str(k)


def _auto_freq(first, last):
    for freq in FREQS:
        if len(_span(_key(first, freq), _key(last, freq), freq, cap=MAX_AUTO_PERIODS)) <= MAX_AUTO_PERIODS:
            return freq
    return "year"


def _numeric_periods(values, freq):
    lo, hi = min(values), max(values)
    distinct = sorted(set(values))
    if freq == "auto" and len(distinct) <= 40:
        labels = [f"{v:g}" for v in distinct]
        return "step", (lambda v: v), distinct, labels
    if freq == "auto":
        width = (hi - lo) / NUMBER_BINS or 1
    elif isinstance(freq, (int, float)) and not isinstance(freq, bool) and freq > 0:
        width = freq
    else:
        raise TarecoError("numeric times need freq='auto' or a positive bin size")
    count = int((hi - lo) // width) + 1
    keys = list(range(count))
    labels = [f"{lo + k * width:g}" for k in keys]
    return "bin", (lambda v: min(int((v - lo) // width), count - 1)), keys, labels

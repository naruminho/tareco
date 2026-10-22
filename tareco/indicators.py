"""Behaviors worth a look in a flow of money (or goods, or messages), in plain network terms.

Amounts far above what a node usually sends, many amounts just under a round
limit, nodes unlike the ones they deal with, nodes close to a list you give,
and where the flow goes by any attribute. The limits and lists come from you:
what counts as "too close to a limit" or "a list to watch" depends on the business.
"""

import datetime as dt
import math
import re
from collections import Counter

from . import i18n
from .errors import TarecoError
from .io import _is_number, _kinds_of, _missing
from .patterns import Pattern, Patterns

TIME_NAMES = ("date", "datetime", "time", "timestamp", "ts", "when", "day", "data", "dia", "dt",
              "created_at", "booked_at", "posted_at", "value_date", "booking_date")
ROUND_STEPS = (1, 2, 3, 5)
CATEGORY_LIMIT = 30


class _Transfer:
    __slots__ = ("u", "v", "amount", "when", "row")

    def __init__(self, u, v, amount, when, row):
        self.u, self.v, self.amount, self.when, self.row = u, v, amount, when, row


def flow_kinds(g):
    """Link kinds that carry a flow (directed), or None when the graph has no kinds."""
    known = g.attrs.get("link_kinds") or {}
    if not known:
        return None
    return {k for k, v in known.items() if v.get("directed")} | {None}


def transfers(g, time=None, need_time=False):
    """The single rows behind the flow links, as transfers with an amount and maybe a time."""
    if not g.attrs.get("kept"):
        raise TarecoError("this needs the single rows behind each link; load the graph with keep=True")
    weight = g.attrs.get("weight")
    if not weight:
        raise TarecoError("which column has the amount? load the graph with weight=... (or amount=...)")
    kinds = flow_kinds(g)
    events = [e for e in g._events if kinds is None or e[2] in kinds]
    rows = [e[3] for e in events]
    if events and weight not in rows[0] and all(weight not in r for r in rows[:50]):
        raise TarecoError(f"the kept rows have no {weight!r} column; keep it too (keep=True keeps everything)")
    column = time_column(rows, time)
    if need_time and column is None:
        raise TarecoError("which column has the date? pass time=...")
    whens = parse_times([r.get(column) for r in rows]) if column else [None] * len(rows)
    out = []
    for (u, v, _, row), when in zip(events, whens):
        x = row.get(weight)
        if _is_number(x) and x != 0 and (when is not None or not need_time):
            out.append(_Transfer(u, v, abs(x), when, row))
    return out


def time_column(rows, time=None):
    """The column with the date of each row: ``time`` if given, else one that looks like a date."""
    if not rows:
        return time
    names = list(dict.fromkeys(k for r in rows[:200] for k in r))
    if time is not None:
        if time not in names:
            raise TarecoError(f"no column {time!r} for time; columns are {names}")
        return time
    def named(c):
        low = str(c).lower()
        return low in TIME_NAMES or low.endswith(("_date", "_at", "_time", "date"))
    for c in sorted(names, key=lambda c: not named(c)):
        sample = [r.get(c) for r in rows[:50] if not _missing(r.get(c))]
        if not sample or (not named(c) and not all(isinstance(v, (dt.date, dt.datetime)) for v in sample)):
            continue
        if all(isinstance(v, (int, float)) for v in sample):
            continue  # numbers are amounts and ids more often than times
        try:
            parse_times(sample)
            return c
        except TarecoError:
            continue
    return None


def parse_times(values):
    from .temporal import _parse_times
    present = [v for v in values if not _missing(v)]
    parsed = iter(_parse_times(present, None)) if present else iter(())
    return [None if _missing(v) else next(parsed) for v in values]


def parse_span(within):
    """"7 days", "48 hours", "2 weeks", "3d", a number of days or a timedelta."""
    if isinstance(within, dt.timedelta):
        return within
    if isinstance(within, (int, float)) and not isinstance(within, bool):
        return dt.timedelta(days=within)
    m = re.match(r"^\s*(\d+(?:\.\d+)?)\s*([a-z]*)\s*$", str(within).lower())
    if m:
        n, unit = float(m.group(1)), m.group(2)
        for names, delta in ((("d", "day", "days", "dia", "dias"), dt.timedelta(days=1)),
                             (("h", "hour", "hours", "hora", "horas"), dt.timedelta(hours=1)),
                             (("w", "week", "weeks", "semana", "semanas"), dt.timedelta(weeks=1))):
            if unit in names or (unit == "" and names[0] == "d"):
                return n * delta
    raise TarecoError(f"cannot read {within!r} as a span of time; try \"7 days\" or \"48 hours\"")


class _Text:
    def __init__(self, g, lang, label):
        self.g = g
        self.lang = i18n.get_language(lang)
        self.label = label

    def __call__(self, key, **kw):
        return i18n.text(self.lang, key, **kw)

    def num(self, v):
        return i18n.number(v, self.lang)

    def name(self, node):
        if self.label is not None:
            value = self.g.nodes[node].get(self.label)
            if value is not None:
                return str(value)
        return str(node)

    def date(self, when):
        if when is None:
            return ""
        if isinstance(when, dt.datetime) and (when.hour or when.minute):
            return when.strftime("%Y-%m-%d %H:%M")
        return when.strftime("%Y-%m-%d") if hasattr(when, "strftime") else str(when)

    def span(self, delta):
        days = delta.total_seconds() / 86400
        if days >= 1:
            n = round(days, 1)
            return self("span_day") if n == 1 else self("span_days", n=self.num(n))
        return self("span_hours", n=self.num(round(delta.total_seconds() / 3600, 1)))

    def join(self, items):
        return i18n.join(items, self.lang)

    def listing(self, items, most=3):
        """"a, b and c", or "a, b, c and 12 more"."""
        items = [str(i) for i in items]
        if len(items) <= most:
            return self.join(items)
        return ", ".join(items[:most]) + self("and_more", k=self.num(len(items) - most))


def _rows(items):
    from .tracing import Rows
    return Rows(dict(t.row) for t in items)


def _quantile(values, q):
    if not values:
        return 0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(q * len(ordered)))]


def _median(values):
    ordered = sorted(values)
    k = len(ordered)
    return ordered[k // 2] if k % 2 else (ordered[k // 2 - 1] + ordered[k // 2]) / 2


# --------------------------------------------------------------- unusual amounts

def unusual_amounts(g, factor=10, min_history=5, time=None, lang=None, label=None, limit=10):
    """Transfers far above what the sender usually sends.

    factor       how many times the sender's usual (median) amount.
    min_history  senders with fewer transfers than this are not judged.
    Only amounts among the largest 5% of the whole network count, so a jump from
    5 to 60 does not.
    """
    T = _Text(g, lang, label)
    items = transfers(g, time)
    cut = _quantile([t.amount for t in items], 0.95)
    by_sender = {}
    for t in items:
        by_sender.setdefault(t.u, []).append(t)
    found = []
    for sender, sent in by_sender.items():
        if len(sent) < min_history:
            continue
        usual = _median([t.amount for t in sent])
        if usual <= 0:
            continue
        for t in sent:
            if t.amount >= factor * usual and t.amount >= cut:
                found.append((t.amount / usual, t, usual))
    found.sort(key=lambda f: (-f[0], str(f[1].u)))
    out = Patterns()
    for ratio, t, usual in found[:limit]:
        when = T("on_date", date=T.date(t.when)) if t.when else ""
        text = T("unusual_amount", name=T.name(t.u), amount=T.num(t.amount), other=T.name(t.v), when=when,
                 times=T.num(round(ratio)), usual=T.num(usual))
        out.append(Pattern("unusual_amount", [t.u, t.v], ratio,
                           {"amount": t.amount, "usual": usual, "when": t.when}, text, _rows([t])))
    return out


# ------------------------------------------------------------------------ splits

def _round_above(amount, margin):
    """The smallest round number (1, 2, 3, 5 x 10^k) above ``amount``, if amount sits just under it."""
    if amount <= 0:
        return None
    e = math.floor(math.log10(amount))
    for limit in sorted(m * 10 ** k for k in (e, e + 1) for m in ROUND_STEPS):
        if limit > amount:
            return limit if amount >= limit * (1 - margin) else None
    return None


def splits(g, limit=None, within="7 days", min_count=3, margin=0.1, time=None, lang=None, label=None,
           top=10):
    """Many amounts just under a limit in a short time, sent or received by one node.

    limit       the amount to stay under (10000). Without it, tareco looks for
                amounts piling up just under any round number (1,000, 3,000,
                5,000, 10,000...) among the larger amounts of the network.
    within      how close in time ("7 days", "48 hours").
    min_count   how many amounts make a pile (at least 5 when tareco looks for the limit).
    margin      how close counts as "just under": 0.1 means within 10%.

    A pile only counts when the amounts gather under the limit, not around it:
    a payroll paying salaries of every size is not splitting anything.
    """
    T = _Text(g, lang, label)
    items = transfers(g, time, need_time=True)
    span = parse_span(within)
    floor = 0 if limit is not None else _quantile([t.amount for t in items], 0.9)
    # without a limit to go by, a pile has to be big to stand out from chance
    need = min_count if limit is not None else max(min_count, 5)
    found = []
    for side in ("out", "in"):
        by_node = {}
        for t in items:
            by_node.setdefault(t.u if side == "out" else t.v, []).append(t)
        for node, mine in by_node.items():
            if len(mine) < need:
                continue
            mine.sort(key=lambda t: t.when)
            limits = [limit] if limit is not None else sorted(
                {x for x in (_round_above(t.amount, margin) for t in mine) if x and x >= floor})
            best = None
            for cap in limits:
                below = [t for t in mine if cap * (1 - margin) <= t.amount < cap]
                if len(below) < need:
                    continue
                j, window = 0, None
                for i in range(len(below)):
                    while below[i].when - below[j].when > span:
                        j += 1
                    if window is None or i - j + 1 > len(window):
                        window = below[j:i + 1]
                if len(window) < need:
                    continue
                first, last = window[0].when, window[-1].when
                inside = [t for t in mine if first <= t.when <= last]
                above = sum(1 for t in inside if cap <= t.amount <= cap * (1 + margin))
                lower = sum(1 for t in inside if cap * (1 - 2 * margin) <= t.amount < cap * (1 - margin))
                if len(window) < need + 2 * (above + lower):
                    continue  # amounts spread around the limit (salaries, shopping), not piling under it
                score = (len(window), sum(t.amount for t in window))
                if best is None or score > best[0]:
                    best = (score, cap, window)
            # money coming in from a single sender is that sender's pile, already counted on its side
            if best and (side == "out" or len({t.u for t in best[2]}) >= 2):
                found.append((best[0], node, side, best[1], best[2]))
    found.sort(key=lambda f: (-f[0][0], -f[0][1], str(f[1])))
    out = Patterns()
    for _, node, side, cap, window in found[:top]:
        others = list(dict.fromkeys(t.v if side == "out" else t.u for t in window))
        amounts = [t.amount for t in window]
        text = T("split_" + side, name=T.name(node), k=T.num(len(window)), limit=T.num(cap),
                 span=T.span(window[-1].when - window[0].when) if window[-1].when > window[0].when
                 else T("span_same_day"), first=T.date(window[0].when), last=T.date(window[-1].when),
                 r=T.num(len(others)), lo=T.num(min(amounts)), hi=T.num(max(amounts)))
        out.append(Pattern("split", [node] + others, len(window),
                           {"limit": cap, "side": side, "count": len(window), "total": sum(amounts),
                            "first": window[0].when, "last": window[-1].when}, text, _rows(window)))
    return out


# ----------------------------------------------------------------------- misfits

def attribute_kinds(g, attrs=None):
    """``{name: "number" | "category"}`` for node attributes worth comparing (ids are left out)."""
    names = attrs if attrs is not None else list(dict.fromkeys(k for d in g._nodes.values() for k in d))
    if isinstance(names, str):
        names = [names]
    out = {}
    for name in names:
        if name in ("kind", "hop"):
            continue
        present = [d[name] for d in g._nodes.values() if not _missing(d.get(name))]
        if len(present) < 3:
            continue
        if all(_is_number(v) for v in present):
            out[name] = "number"
        else:
            distinct = len({str(v) for v in present})
            if 2 <= distinct <= CATEGORY_LIMIT and distinct <= 0.6 * len(present):
                out[name] = "category"
    return out


def misfits(g, attrs=None, factor=10, min_neighbors=3, lang=None, label=None, limit=10):
    """Nodes unlike the nodes they deal with: much lower or higher numbers, or a rare category.

    attrs          node attributes to compare (default: every number and category).
    factor         for numbers, how many times above or below the neighbors' median.
    min_neighbors  neighbors with the attribute needed to judge a node.

    Neighbors are compared with nodes of the same kind (accounts with accounts),
    whatever the link between them.
    """
    T = _Text(g, lang, label)
    kinds = attribute_kinds(g, attrs)
    if attrs is not None:
        missing = [a for a in ([attrs] if isinstance(attrs, str) else attrs) if a not in kinds]
        if missing:
            raise TarecoError(f"{missing[0]!r} is not a node attribute with numbers or categories")
    found = []
    for x in g:
        own = g._nodes[x]
        kx = own.get("kind")
        nbrs = [y for y in g._all_neighbors(x) if y != x and g._nodes[y].get("kind") == kx]
        for name, kind in kinds.items():
            value = own.get(name)
            if _missing(value):
                continue
            values = [g._nodes[y].get(name) for y in nbrs if not _missing(g._nodes[y].get(name))]
            if len(values) < min_neighbors:
                continue
            if kind == "number":
                if not _is_number(value) or value <= 0:
                    continue
                med = _median([v for v in values if _is_number(v)] or [0])
                if med <= 0:
                    continue
                ratio = max(value / med, med / value)
                if ratio < factor:
                    continue
                key = "misfit_lower" if value < med else "misfit_higher"
                text = T(key, name=T.name(x), attr=name, value=T.num(value), times=T.num(round(ratio)),
                         k=T.num(len(values)), median=T.num(med))
                found.append((math.log2(ratio) * math.sqrt(len(values)), x, name, text, med))
            else:
                if len(values) < max(min_neighbors, 5):
                    continue  # with three neighbors, all from one city happens by chance
                counts = Counter(str(v) for v in values)
                share = counts.get(str(value), 0) / len(values)
                top, c = counts.most_common(1)[0]
                if share > 0.1 or c / len(values) < 0.7 or top == str(value):
                    continue
                text = T("misfit_category", name=T.name(x), attr=name, value=value, other=top,
                         pct=i18n.percent(c / len(values), T.lang), k=T.num(len(values)))
                found.append(((1 - share) * math.sqrt(len(values)), x, name, text, top))
    found.sort(key=lambda f: (-f[0], str(f[1])))
    out = Patterns()
    for score, x, name, text, typical in found[:limit]:
        nbrs = [y for y in g._all_neighbors(x) if y != x and g._nodes[y].get("kind") == g._nodes[x].get("kind")]
        out.append(Pattern("misfit", [x] + nbrs, score, {"attribute": name, "typical": typical}, text))
    return out


# -------------------------------------------------------------------------- near

def targets_of(g, targets):
    """Nodes from a node, a list of nodes, a predicate ``(node, attrs)`` or a true/false attribute."""
    if callable(targets):
        return [n for n, d in g._nodes.items() if targets(n, d)]
    if isinstance(targets, (list, tuple, set, frozenset)):
        return [n for n in dict.fromkeys(targets) if n in g]
    if targets in g:
        return [targets]
    if isinstance(targets, str) and any(targets in d for d in g._nodes.values()):
        return [n for n, d in g._nodes.items() if d.get(targets) in (True, 1, "yes", "true", "sim")]
    raise TarecoError(f"{targets!r} is neither a node nor a true/false attribute of the nodes")


def near(g, targets, hops=2, lang=None, label=None, limit=10, kinds=None):
    """Nodes within ``hops`` steps of a list you give (flagged accounts, known cases).

    targets   a node, a list of nodes, an attribute that is true for them
              ("flagged") or a predicate ``(node, attrs)``.
    kinds     node kinds to report (default: the kinds of the targets, so a list
              of accounts brings back accounts, not the devices in between).

    Direction is ignored, and paths do not go through hubs (a payroll account,
    a big shop): everybody is a couple of steps from them.
    """
    T = _Text(g, lang, label)
    start = targets_of(g, targets)
    if not start:
        raise TarecoError("none of the targets is in the graph")
    degree = {x: len(set(g._all_neighbors(x)) - {x}) for x in g}
    active = [d for d in degree.values() if d > 0]
    hub = max(20, 5 * _median(active)) if active else 20
    wanted = set(kinds) if kinds is not None else ({g._nodes[t].get("kind") for t in start})
    dist = {t: 0 for t in start}
    origin = {t: {t} for t in start}
    prev = {t: None for t in start}
    frontier = list(start)
    for h in range(1, hops + 1):
        nxt = []
        for u in frontier:
            if dist[u] >= 1 and degree[u] >= hub:
                continue
            for v in g._all_neighbors(u):
                if v not in dist:
                    dist[v], origin[v], prev[v] = h, set(origin[u]), u
                    nxt.append(v)
                elif dist[v] == h:
                    origin[v] |= origin[u]
        frontier = nxt
    found = []
    order = {n: i for i, n in enumerate(g)}
    for x, d in dist.items():
        if d == 0 or g._nodes[x].get("kind") not in wanted:
            continue
        found.append((len(origin[x]) / d, x, d))
    found.sort(key=lambda f: (-f[0], f[2], order[f[1]]))
    out = Patterns()
    for score, x, d in found[:limit]:
        hits = sorted(origin[x], key=order.get)
        shown = T.listing([T.name(t) for t in hits])
        via = []
        cur = prev[x]
        while cur is not None and prev[cur] is not None:
            kind = g._nodes[cur].get("kind")
            via.append(f"{T.name(cur)} ({kind})" if kind else T.name(cur))
            cur = prev[cur]
        if d == 1:
            text = T("near_direct", name=T.name(x), targets=shown)
        else:
            text = T("near", name=T.name(x), d=T.num(d), targets=shown, via=T.join(via))
        out.append(Pattern("near", [x] + hits, score, {"steps": d, "targets": hits}, text))
    return out


# ------------------------------------------------------------------------- flows

class Flow:
    __slots__ = ("value", "amount", "share", "links", "nodes")

    def __init__(self, value, amount, share, links, nodes):
        self.value, self.amount, self.share, self.links, self.nodes = value, amount, share, links, nodes

    def to_dict(self):
        return {k: getattr(self, k) for k in self.__slots__}


class Flows(list):
    """How the flow splits by an attribute, biggest first."""

    def __init__(self, items=(), title="", lang="en", direction="to", label=None, g=None):
        super().__init__(items)
        self.title = title
        self._lang = lang
        self._direction = direction
        self._label = label
        self._g = g

    def __getitem__(self, key):
        if isinstance(key, (int, slice)):
            return list.__getitem__(self, key)
        for f in self:
            if f.value == key or str(f.value) == str(key):
                return f
        raise KeyError(key)

    def __repr__(self):
        T = _Text(self._g, self._lang, self._label) if self._g is not None else None
        lines = [self.title]
        for f in self:
            names = T.listing([T.name(n) for n in f.nodes]) if T else ", ".join(map(str, f.nodes[:3]))
            value = i18n.text(self._lang, "nobody") if f.value is None else f.value
            lines.append("- " + i18n.text(self._lang, "flow_line" if self._direction == "to" else "flow_line_from",
                                          value=value, amount=i18n.number(f.amount, self._lang),
                                          share=i18n.percent(f.share, self._lang),
                                          links=i18n.number(f.links, self._lang),
                                          k=i18n.number(len(f.nodes), self._lang), names=names))
        return "\n".join(lines)

    def to_pandas(self):
        try:
            import pandas as pd
        except ImportError:
            raise TarecoError("to_pandas needs pandas: pip install pandas") from None
        return pd.DataFrame([{**f.to_dict(), "nodes": list(f.nodes)} for f in self])


def flows(g, by, direction="to", weight="weight", lang=None, label=None):
    """How much of the flow goes to (or comes from) each value of an attribute.

    by          a link attribute (a country column of the transfers) or a node
                attribute of the receiving node ("to") or the sending node ("from").
    direction   "to": where it goes, by the receiver; "from": where it comes from.

    Each item has ``value``, ``amount``, ``share``, ``links`` and ``nodes`` (the
    senders for "to", the receivers for "from", biggest first).
    """
    if direction not in ("to", "from"):
        raise TarecoError('direction must be "to" or "from"')
    from .graph import _weight_fn
    T = _Text(g, lang, label)
    wt = _weight_fn(weight, g)
    kinds = flow_kinds(g)
    agg = {}
    total = 0.0
    for u, v, d in g._edge_triples():
        if kinds is not None and not (set(_kinds_of(d)) or {None}) & kinds:
            continue
        key = d.get(by) if by in d else g._nodes[v if direction == "to" else u].get(by)
        w = wt(d)
        w = w if _is_number(w) else 1
        entry = agg.setdefault(None if _missing(key) else key, [0.0, 0, {}])
        entry[0] += w
        entry[1] += 1
        other = u if direction == "to" else v
        entry[2][other] = entry[2].get(other, 0) + w
        total += w
    items = []
    for key, (amount, links, per) in agg.items():
        nodes = sorted(per, key=lambda n: -per[n])
        items.append(Flow(key, amount, amount / total if total else 0, links, nodes))
    items.sort(key=lambda f: -f.amount)
    title = T("flows_title" if direction == "to" else "flows_title_from", by=by)
    return Flows(items, title, T.lang, direction, label, g)

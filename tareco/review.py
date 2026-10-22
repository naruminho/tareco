"""Everything worth a look, gathered per node and ranked: a work list for whoever investigates."""

from . import i18n
from .errors import TarecoError
from .indicators import _Text, misfits, near, splits, unusual_amounts
from .patterns import find_patterns
from .tracing import Rows
from .tuning import setting

# how much each kind of signal weighs, and what a second one of a kind adds: see tareco.settings
ID_WORDS = ("id", "tid", "txid", "uuid", "guid")


class Signal:
    __slots__ = ("kind", "text", "rows")

    def __init__(self, kind, text, rows):
        self.kind, self.text, self.rows = kind, text, rows

    def __repr__(self):
        return self.text


def signals(g, watch=None, limit=None, within=None, lang=None, label=None):
    """``{node: [Signal, ...]}``: every pattern and behavior found, attached to the nodes it is about."""
    key = ("signals", tuple(watch) if isinstance(watch, (list, tuple)) else watch, limit, str(within), lang, label)
    return g._cached(key, lambda: _signals(g, watch, limit, within, lang, label))


def _signals(g, watch, limit, within, lang, label):
    from .investigate import _exclusive
    found = {}

    def add(node, kind, text, rows=()):
        found.setdefault(node, []).append(Signal(kind, text, Rows(rows)))

    found_patterns = find_patterns(g, lang=lang, label=label, limit=200)
    best_loop = max((p.score for p in found_patterns if p.kind == "cycle"), default=0)
    for p in found_patterns:
        if p.kind == "cycle" and p.score < 0.25 * best_loop:
            continue  # small change going around is everyday; explain() keeps the same ones
        if p.kind == "cycle":
            for x in p.nodes:
                add(x, p.kind, p.text)
        elif p.kind == "chain":
            for x in p.nodes[1:-1]:
                add(x, p.kind, p.text)
        elif p.kind in ("pass_through", "fan_in", "fan_out") and _exclusive(p):
            add(p.nodes[0], p.kind, p.text)
        elif p.kind == "shared":
            for x in p.nodes[1:]:
                add(x, p.kind, p.text)
    if g.attrs.get("kept"):
        for look in (lambda: splits(g, limit=limit, within=within, lang=lang, label=label, top=1000),
                     lambda: unusual_amounts(g, lang=lang, label=label, limit=1000),
                     lambda: _fast(g, within, lang, label)):
            try:
                for p in look():
                    add(p.nodes[0], p.kind, p.text, p.rows)
            except TarecoError:
                pass  # no dates or no amounts: those signals cannot be looked for
    for p in misfits(g, lang=lang, label=label, limit=1000):
        add(p.nodes[0], p.kind, p.text)
    if watch is not None:
        for p in near(g, watch, lang=lang, label=label, limit=10 ** 6):
            add(p.nodes[0], p.kind, p.text)
    return found


def _fast(g, within, lang, label):
    try:
        from .indicators import fast_moves
    except ImportError:
        return []
    return fast_moves(g, lang=lang, label=label, limit=1000)


class ReviewItem:
    __slots__ = ("node", "score", "signals", "rows", "ids", "_lang")

    def __init__(self, node, score, signals, rows, ids, lang="en"):
        self.node, self.score, self.signals, self.rows, self.ids = node, score, signals, rows, ids
        self._lang = lang

    @property
    def reasons(self):
        """One line per kind of signal: the strongest, and how many more like it."""
        return [text for _, text in self.summary()]

    def summary(self, lang="en"):
        def key(s):
            return s.text if s.kind == "misfit" else s.kind  # misfits differ by attribute

        out, counts = [], {}
        for s in self.signals:
            counts[key(s)] = counts.get(key(s), 0) + 1
        shown = set()
        for s in self.signals:
            if key(s) in shown:
                continue
            shown.add(key(s))
            more = counts[key(s)] - 1
            out.append((s.kind, s.text + (i18n.text(self._lang, "review_more", k=i18n.number(more, self._lang))
                                          if more else "")))
        return out

    def __repr__(self):
        return f"{self.node!r} ({self.score})"


class Review(list):
    """Nodes worth a look, the strongest case first, each with its reasons and the rows behind them."""

    def __init__(self, items=(), title="", lang="en", g=None, label=None, id_column=None):
        super().__init__(items)
        self.title = title
        self._lang = lang
        self._g = g
        self._label = label
        self.id_column = id_column

    @property
    def nodes(self):
        return [r.node for r in self]

    def __repr__(self):
        T = _Text(self._g, self._lang, self._label)
        lines = [self.title]
        for k, r in enumerate(self, 1):
            extra = T("review_rows", k=T.num(len(r.rows))) if r.rows else ""
            lines.append(f"{k}. " + T("review_item", name=T.name(r.node), score=T.num(r.score)) + extra)
            lines += [f"   - {text}" for text in r.reasons]
        return "\n".join(lines)

    def table(self):
        """One dict per node: ``node``, ``score``, ``signals``, ``reasons``, ``rows``, ``ids`` and its attributes."""
        out = []
        for r in self:
            attrs = self._g.nodes[r.node] if self._g is not None else {}
            out.append({"node": r.node, "score": r.score,
                        "signals": ", ".join(dict.fromkeys(s.kind for s in r.signals)),
                        "reasons": " | ".join(r.reasons), "rows": len(r.rows),
                        "ids": ", ".join(map(str, r.ids)), **{k: v for k, v in attrs.items() if k not in
                                                              ("node", "score", "signals", "reasons", "rows",
                                                               "ids")}})
        return out

    def to_pandas(self):
        try:
            import pandas as pd
        except ImportError:
            raise TarecoError("to_pandas needs pandas: pip install pandas") from None
        return pd.DataFrame(self.table())

    def to_spark(self, spark):
        """The list as a Spark DataFrame, to save next to the data (``.write.saveAsTable(...)``)."""
        rows = self.table()
        if not rows:
            raise TarecoError("nothing to review")
        columns = list(dict.fromkeys(k for r in rows for k in r))
        plain = [{c: (r.get(c) if c == "score" or c == "rows" else (None if r.get(c) is None else str(r.get(c))))
                  for c in columns} for r in rows]
        from pyspark.sql.types import DoubleType, LongType, StringType, StructField, StructType
        kinds = {"score": DoubleType(), "rows": LongType()}
        schema = StructType([StructField(c, kinds.get(c, StringType()), True) for c in columns])
        return spark.createDataFrame([[r[c] for c in columns] for r in plain], schema)

    def compare(self, previous):
        """What changed since an earlier work list: who is new, whose score went up or
        down, and who left it.

        ``previous`` is an earlier Review, or the table one was saved as: its
        ``to_pandas()``, a CSV, a Spark table, a list of dicts. It needs the
        ``node`` and ``score`` columns; with ``signals`` too, a node that went up
        shows the reasons that are new.
        """
        before = _earlier(previous)
        by_text = {str(k): k for k in before}
        new, up, down, same = [], [], [], []
        seen = set()
        for r in self:
            key = r.node if r.node in before else by_text.get(str(r.node))
            if key is None:
                new.append(r)
                continue
            seen.add(key)
            score, kinds = before[key]
            fresh = [text for kind, text in r.summary() if kinds is not None and kind not in kinds]
            if r.score > score + 0.005:
                up.append((r, score, fresh))
            elif r.score < score - 0.005:
                down.append((r, score, fresh))
            else:
                same.append(r)
        gone = [(k, before[k][0]) for k in before if k not in seen]
        return Changes(new, up, down, gone, same, self._lang, self._g, self._label)


def _earlier(previous):
    """``{node: (score, set of signal kinds or None)}`` from a Review or a saved table."""
    if isinstance(previous, Review):
        return {r.node: (r.score, {s.kind for s in r.signals}) for r in previous}
    from .io import iter_table
    columns, rows = iter_table(previous)
    for c in ("node", "score"):
        if rows and c not in columns:
            raise TarecoError(f"an earlier review needs the column {c!r}; the table has {columns}")
    out = {}
    for r in rows:
        kinds = r.get("signals")
        kinds = None if kinds is None else {k.strip() for k in str(kinds).split(",") if k.strip()}
        out[r["node"]] = (float(r["score"]), kinds)
    return out


class Changes:
    """What changed between two work lists: ``new``, ``up`` and ``down`` (with the score
    before), ``gone`` (nodes no longer in the list, with the score they had) and ``same``."""

    def __init__(self, new, up, down, gone, same, lang="en", g=None, label=None):
        self.new, self.up, self.down, self.gone, self.same = new, up, down, gone, same
        self._lang, self._g, self._label = lang, g, label

    @property
    def nodes(self):
        """What to look at now: the new ones, then the ones that went up."""
        return [r.node for r in self.new] + [r.node for r, _, _ in self.up]

    def __bool__(self):
        return bool(self.new or self.up or self.down or self.gone)

    def __repr__(self):
        T = _Text(self._g, self._lang, self._label)
        if not self:
            return T("changes_none")
        lines = [T("changes_title")]
        if self.new:
            lines.append(T("changes_new", k=T.num(len(self.new))))
            for r in self.new:
                lines.append("- " + T("review_item", name=T.name(r.node), score=T.num(r.score)))
                lines += [f"   - {text}" for text in r.reasons[:3]]
        for key, items in (("changes_up", self.up), ("changes_down", self.down)):
            if items:
                lines.append(T(key, k=T.num(len(items))))
                for r, before, fresh in items:
                    lines.append("- " + T("changes_moved", name=T.name(r.node), before=T.num(before),
                                          after=T.num(r.score)))
                    lines += [f"   - {text}" for text in fresh[:3]]
        if self.gone:
            lines.append(T("changes_gone", k=T.num(len(self.gone))))
            lines += ["- " + T("changes_was", name=T.name(n), score=T.num(s)) for n, s in self.gone]
        return "\n".join(lines)

    def table(self):
        """One dict per node that changed: ``node``, ``change``, ``score``, ``before`` and ``reasons``."""
        out = [{"node": r.node, "change": "new", "score": r.score, "before": None, "reasons": " | ".join(r.reasons)}
               for r in self.new]
        for change, items in (("up", self.up), ("down", self.down)):
            out += [{"node": r.node, "change": change, "score": r.score, "before": before,
                     "reasons": " | ".join(fresh or r.reasons)} for r, before, fresh in items]
        out += [{"node": n, "change": "gone", "score": None, "before": s, "reasons": ""} for n, s in self.gone]
        return out

    def to_pandas(self):
        """``table()`` as a pandas DataFrame."""
        try:
            import pandas as pd
        except ImportError:
            raise TarecoError("to_pandas needs pandas: pip install pandas") from None
        return pd.DataFrame(self.table(), columns=["node", "change", "score", "before", "reasons"])


def _id_column(rows):
    for r in rows[:50]:
        for k in r:
            words = set(str(k).lower().replace("-", "_").split("_"))
            if words & set(ID_WORDS) or str(k).lower().endswith("id"):
                return k
    return None


def review(g, watch=None, limit=None, within=None, top=50, lang=None, label=None, found=None):
    """Every node something stands out about, ranked, with its reasons and the rows behind them.

    watch   a list to check closeness to (flagged nodes, known cases), as in ``near``.
    limit   the amount to stay under for ``splits`` (default: any round amount).
    within  how close in time for piles and fast in-and-out moves.
    top     how many nodes to keep.

    The score adds up the signals: piles under a limit weigh most, then money passed
    on fast, unusual amounts, loops, chains and pass-throughs, then misfits,
    closeness to the list and things shared with others. ``to_pandas()`` and
    ``to_spark(spark)`` turn it into a table to work from.
    """
    T = _Text(g, lang, label)
    if found is None:
        found = signals(g, watch=watch, limit=limit, within=within, lang=T.lang, label=label)
    kept = [e[3] for e in g._events[:200]] if g.attrs.get("kept") else []
    id_column = _id_column(kept)
    weights, repeat, cap = setting("weights"), setting("repeat"), setting("repeat_cap")
    items = []
    for node, sigs in found.items():
        extra, score = {}, 0.0
        for s in sigs:
            if s.kind not in extra:
                score += weights.get(s.kind, 1.0)
                extra[s.kind] = 0.0
            elif extra[s.kind] < cap:
                score += repeat
                extra[s.kind] += repeat
        rows = Rows()
        keys = set()
        for s in sigs:
            for r in s.rows:
                key = tuple(sorted((str(k), repr(v)) for k, v in r.items()))
                if key not in keys:
                    keys.add(key)
                    rows.append(r)
        ids = [r.get(id_column) for r in rows] if id_column else []
        sigs = sorted(sigs, key=lambda s: -weights.get(s.kind, 1.0))
        items.append(ReviewItem(node, round(score, 2), sigs, rows, ids, T.lang))
    order = {n: i for i, n in enumerate(g)}
    items.sort(key=lambda r: (-r.score, order.get(r.node, 0)))
    return Review(items[:top], T("review_title"), T.lang, g, label, id_column)

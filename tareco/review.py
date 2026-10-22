"""Everything worth a look, gathered per node and ranked: a work list for whoever investigates."""

from . import i18n
from .errors import TarecoError
from .indicators import _Text, misfits, near, splits, unusual_amounts
from .patterns import find_patterns
from .tracing import Rows

# how much each kind of signal weighs in the ranking; a second signal of the same kind adds a little
WEIGHTS = {"split": 3.0, "fast_pass": 2.5, "unusual_amount": 2.0, "cycle": 2.0, "chain": 2.0,
           "pass_through": 2.0, "fan_in": 2.0, "fan_out": 1.5, "misfit": 1.5, "near": 1.5, "shared": 1.0}
REPEAT = 0.25        # per extra signal of a kind already counted
REPEAT_CAP = 0.5     # ... and no more than this per kind: twenty loops are one story
ID_WORDS = ("id", "tid", "txid", "uuid", "guid")


class Signal:
    __slots__ = ("kind", "text", "rows")

    def __init__(self, kind, text, rows):
        self.kind, self.text, self.rows = kind, text, rows

    def __repr__(self):
        return self.text


def signals(g, watch=None, limit=None, within="7 days", lang=None, label=None):
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


def _id_column(rows):
    for r in rows[:50]:
        for k in r:
            words = set(str(k).lower().replace("-", "_").split("_"))
            if words & set(ID_WORDS) or str(k).lower().endswith("id"):
                return k
    return None


def review(g, watch=None, limit=None, within="7 days", top=50, lang=None, label=None, found=None):
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
    items = []
    for node, sigs in found.items():
        extra, score = {}, 0.0
        for s in sigs:
            if s.kind not in extra:
                score += WEIGHTS.get(s.kind, 1.0)
                extra[s.kind] = 0.0
            elif extra[s.kind] < REPEAT_CAP:
                score += REPEAT
                extra[s.kind] += REPEAT
        rows = Rows()
        keys = set()
        for s in sigs:
            for r in s.rows:
                key = tuple(sorted((str(k), repr(v)) for k, v in r.items()))
                if key not in keys:
                    keys.add(key)
                    rows.append(r)
        ids = [r.get(id_column) for r in rows] if id_column else []
        sigs = sorted(sigs, key=lambda s: -WEIGHTS.get(s.kind, 1.0))
        items.append(ReviewItem(node, round(score, 2), sigs, rows, ids, T.lang))
    order = {n: i for i, n in enumerate(g)}
    items.sort(key=lambda r: (-r.score, order.get(r.node, 0)))
    return Review(items[:top], T("review_title"), T.lang, g, label, id_column)

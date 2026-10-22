"""A look at a table before it becomes a graph: what in it would mislead the analysis.

Real tables carry placeholders ("N/A", "0", "UNKNOWN") that tie thousands of
unrelated rows to one fake node, the same id written two ways ("123" and 123,
"ACME " and "acme"), duplicated rows, dates nobody can read. ``check`` lists
them, with how many rows each one touches.
"""

import re

from . import i18n
from .errors import TarecoError
from .io import (MAX_ROWS, SOURCE_COLUMNS, TARGET_COLUMNS, _is_number, _missing, _pick_column, guess_weight,
                 iter_table, looks_like_placeholder)


class Issue:
    __slots__ = ("kind", "text", "count", "examples")

    def __init__(self, kind, text, count, examples=()):
        self.kind, self.text, self.count, self.examples = kind, text, count, list(examples)

    def __repr__(self):
        return self.text


class Check(list):
    """What to fix in a table before trusting a graph made from it. Empty means nothing to fix."""

    def __init__(self, items=(), lang="en", rows=0):
        super().__init__(items)
        self._lang = lang
        self.rows = rows

    @property
    def ok(self):
        return not self

    def __repr__(self):
        T = lambda key, **kw: i18n.text(self._lang, key, **kw)  # noqa: E731
        if not self:
            return T("check_ok", rows=i18n.number(self.rows, self._lang))
        lines = [T("check_title", rows=i18n.number(self.rows, self._lang), k=i18n.number(len(self), self._lang))]
        lines += [f"- {issue.text}" for issue in self]
        return "\n".join(lines)

    def to_pandas(self):
        try:
            import pandas as pd
        except ImportError:
            raise TarecoError("to_pandas needs pandas: pip install pandas") from None
        return pd.DataFrame([{"kind": i.kind, "rows": i.count, "examples": ", ".join(map(str, i.examples)),
                              "text": i.text} for i in self])


def check(data, source=None, target=None, account=None, counterparty=None, amount=None, time=None,
          lang=None, max_rows=MAX_ROWS):
    """What in ``data`` would mislead a graph made from it, with how many rows each thing touches.

    Takes the same tables and column options as ``Graph`` (``account``/``counterparty``
    for statements). Looks for rows without both ends, placeholder ids ("N/A", "0",
    "UNKNOWN"), links from a node to itself, duplicated rows, ids written two ways
    ("123" and 123, "ACME " and "acme"), amounts that are text or zero, statements
    with no money out, and dates that cannot be read.
    """
    lang = i18n.get_language(lang)
    num = lambda v: i18n.number(v, lang)  # noqa: E731
    T = lambda key, **kw: i18n.text(lang, key, **kw)  # noqa: E731
    columns, rows = iter_table(data, max_rows)
    rows = [r for r in rows if r]
    statement = account is not None or counterparty is not None
    if statement:
        if account is None or counterparty is None:
            raise TarecoError("a statement needs both account= and counterparty=")
        s, t = account, counterparty
        for c in (s, t):
            if c not in columns:
                raise TarecoError(f"no column {c!r}; columns are {columns}")
    else:
        s = _pick_column(columns, source, SOURCE_COLUMNS, "source")
        t = _pick_column(columns, target, TARGET_COLUMNS, "target", exclude=s)
    issues = []
    n = len(rows)

    missing = sum(1 for r in rows if _missing(r.get(s)) or _missing(r.get(t)))
    if missing:
        issues.append(Issue("missing", T("check_missing", k=num(missing), s=s, t=t), missing))

    for col in dict.fromkeys((s, t)):
        counts = {}
        for r in rows:
            v = r.get(col)
            if not _missing(v) and looks_like_placeholder(v):
                counts[v] = counts.get(v, 0) + 1
        if counts:
            worst = sorted(counts, key=lambda v: -counts[v])
            total = sum(counts.values())
            names = i18n.join([repr(v) for v in worst[:3]], lang)
            issues.append(Issue("placeholder", T("check_placeholder", k=num(total), col=col, names=names),
                                total, worst[:5]))

    loops = sum(1 for r in rows if not _missing(r.get(s)) and r.get(s) == r.get(t))
    if loops:
        issues.append(Issue("self", T("check_self", k=num(loops)), loops))

    seen, dups = set(), 0
    for r in rows:
        key = tuple(sorted((str(k), repr(v)) for k, v in r.items()))
        if key in seen:
            dups += 1
        seen.add(key)
    if dups:
        issues.append(Issue("duplicates", T("check_duplicates", k=num(dups)), dups))

    ids = [r.get(c) for r in rows for c in dict.fromkeys((s, t)) if not _missing(r.get(c))]
    numbers = {v for v in ids if _is_number(v)}
    texts = {v for v in ids if isinstance(v, str)}
    both = sorted({str(v) for v in numbers} & texts) or \
        sorted({str(int(v)) for v in numbers if float(v).is_integer()} & texts)
    if both:
        issues.append(Issue("mixed_types", T("check_mixed", k=num(len(both)), names=i18n.join(both[:3], lang)),
                            len(both), both[:5]))
    variants = {}
    for v in texts:
        variants.setdefault(re.sub(r"\s+", " ", v.strip().lower()), set()).add(v)
    twins = [sorted(group) for group in variants.values() if len(group) > 1]
    if twins:
        shown = i18n.join([" / ".join(repr(x) for x in group[:2]) for group in twins[:2]], lang)
        issues.append(Issue("variants", T("check_variants", k=num(len(twins)), names=shown), len(twins),
                            [g[0] for g in twins[:5]]))

    rest = [c for c in columns if c not in (s, t)]
    money = amount if amount is not None else guess_weight(rest, lambda c: (r.get(c) for r in rows
                                                                            if _is_number(r.get(c))))
    if money is not None:
        if money not in columns:
            raise TarecoError(f"no column {money!r}; columns are {columns}")
        values = [r.get(money) for r in rows if not _missing(r.get(money))]
        text = [v for v in values if not _is_number(v)]
        if text:
            issues.append(Issue("amount_text", T("check_amount_text", k=num(len(text)), col=money,
                                                 names=i18n.join([repr(v) for v in text[:3]], lang)), len(text),
                                text[:5]))
        zeros = sum(1 for v in values if _is_number(v) and v == 0)
        if zeros:
            issues.append(Issue("amount_zero", T("check_amount_zero", k=num(zeros), col=money), zeros))
        if statement and values and all(not _is_number(v) or v >= 0 for v in values):
            issues.append(Issue("no_money_out", T("check_no_money_out", col=money), len(values)))

    from .indicators import time_column
    when = time_column(rows, time, strict=False)
    if when is not None:
        from .temporal import DMY, _as_datetime
        bad = [v for v in (r.get(when) for r in rows) if not _missing(v) and not isinstance(v, (int, float))
               and _as_datetime(v) is None and not (isinstance(v, str) and DMY.match(v))]
        if bad:
            issues.append(Issue("dates", T("check_dates", k=num(len(bad)), col=when,
                                           names=i18n.join([repr(v) for v in bad[:3]], lang)), len(bad), bad[:5]))
    return Check(issues, lang, n)

"""Reading graphs from whatever the user has, and writing them back out."""

import csv
import json
import os
import re
import warnings
from decimal import Decimal

from .errors import TarecoError

SOURCE_COLUMNS = ("source", "from", "src", "origin", "origem", "de", "sender",
                  "start", "parent", "u", "node1")
TARGET_COLUMNS = ("target", "to", "dst", "destination", "dest", "destino", "para",
                  "receiver", "end", "child", "v", "node2")
ID_COLUMNS = ("id", "node", "name", "key", "label", "nome", "conta", "account", "cliente", "customer",
              "usuario", "user", "pessoa", "person", "codigo", "code")
PAIRED = {"u": "v", "v": "u", "node1": "node2", "node2": "node1"}
WEIGHT_COLUMNS = ("weight", "peso", "valor", "value", "amount", "quantidade", "qtd", "count", "total",
                  "montante", "quantity")
NOT_WEIGHT = {"id", "ids", "key", "code", "codigo", "cod", "number", "numero", "index", "seq", "order", "rank",
              "date", "data", "time", "timestamp", "ts", "year", "ano", "month", "mes", "week", "semana", "day",
              "dia", "hour", "hora", "since", "until", "zip", "cep", "lat", "lon", "latitude", "longitude", "phone",
              "tid", "txid", "uuid", "guid"}
DECIMAL_COMMA = re.compile(r"^-?\d+,\d+$")
MAX_ROWS = 1_000_000


TABLE_OPTIONS = ("kind", "keep", "account", "counterparty", "amount", "source_kind", "target_kind", "skip")
PLACEHOLDERS = {"", "na", "n/a", "n.a.", "n.a", "null", "none", "nil", "nan", "unknown", "undefined", "missing",
                "not available", "tbd", "default", "desconhecido", "nao informado", "não informado",
                "sem informacao", "sem informação", "nd", "n/d", "s/n", "-", "--", "?", "0", "-1"}
_FILLER = re.compile(r"^(0+|9{3,}|x{3,}|-+|\?+|\.+|\*+)$", re.I)
ROLE_WORDS = set(SOURCE_COLUMNS) | set(TARGET_COLUMNS) | {
    "id", "node", "name", "key", "a", "b", "x", "y", "left", "right", "first", "second", "other"}


def load_into(g, data, *, directed=None, nodes=None, source=None, target=None, node_id=None,
              max_rows=MAX_ROWS, **table):
    data = _resolve(data)
    statement = table.get("account") is not None or table.get("counterparty") is not None
    asked = directed
    if directed is None:
        directed = True if statement else _infer_directed(data)
    g._reset(bool(directed))
    if nodes is not None:
        _add_nodes_from(g, _resolve(nodes), node_id, max_rows)
    if data is not None:
        _add_data(g, data, source, target, node_id, max_rows, {**table, "directed": asked})


def add_links(g, data, *, source=None, target=None, directed=None, nodes=None, node_id=None,
              max_rows=MAX_ROWS, **table):
    """``Graph.add_links``: one more table of links, possibly of another kind, into ``g``."""
    if nodes is not None:
        _add_nodes_from(g, _resolve(nodes), node_id, max_rows)
    columns, rows = iter_table(data, max_rows)
    _add_edge_records(g, rows, source, target, columns, directed=directed, **table)
    choose_weight(g)


class GuessWarning(UserWarning):
    """tareco had to guess which column means what."""


class DataWarning(UserWarning):
    """Something in the data will mislead the analysis, like a placeholder id tying everything together."""


def looks_like_placeholder(value):
    """"N/A", "UNKNOWN", "0", "-1", "99999", "XXX": ids that stand for "nobody knows"."""
    if isinstance(value, bool) or value is None:
        return False
    if isinstance(value, (int, float)):
        if value != value:
            return False
        return value in (0, -1) or (abs(value) >= 999 and set(str(int(abs(value)))) == {"9"})
    text = str(value).strip().lower()
    return text in PLACEHOLDERS or bool(_FILLER.match(text))


class _Watch:
    """Counts placeholder-looking ids while a table loads, and warns about the ones that tie many rows."""

    def __init__(self):
        self.counts = {}
        self.rows = 0

    def see(self, u, v):
        self.rows += 1
        for value, role in ((u, "source"), (v, "target")):
            if looks_like_placeholder(value):
                key = (value, role)
                self.counts[key] = self.counts.get(key, 0) + 1

    def finish(self):
        for (value, role), k in sorted(self.counts.items(), key=lambda kv: -kv[1]):
            if k >= max(20, 0.01 * self.rows):
                warnings.warn(f"{value!r} is the {role} of {k:,} rows; it looks like a placeholder and ties "
                              f"unrelated nodes together. Pass skip=[{value!r}] to leave those rows out "
                              f"(tareco.check(table) lists what else to fix)", DataWarning, stacklevel=5)


def choose_weight(g, weight=None):
    """Remember which edge attribute is the weight: the one asked for, or an obvious one."""
    names = list(dict.fromkeys(k for _, _, d in g._edge_triples() for k in d))
    if weight is not None:
        if weight not in names and g.edge_count:
            raise TarecoError(f"no edge column {weight!r} for weight; edge columns are {names}")
        g.attrs["weight"] = weight
        return
    if "weight" in g.attrs or "weight" in names or not g.edge_count:
        return
    found = guess_weight(names, lambda n: (d[n] for _, _, d in g._edge_triples() if n in d))
    if found is not None:
        g.attrs["weight"] = found


def guess_weight(names, values):
    """The column that is obviously the weight, or None. ``values(name)`` gives that column's values."""
    numbers = []
    for n in names:
        present = [v for v in values(n) if not _missing(v)]
        if present and all(_is_number(v) for v in present):
            numbers.append(n)
    plain = {n: str(n).strip().lower() for n in numbers}
    named = [n for n in numbers if plain[n] in WEIGHT_COLUMNS and plain[n] != "count"]
    others = [n for n in numbers if plain[n] not in WEIGHT_COLUMNS and not _labels_something(n)]
    counts = [n for n in numbers if plain[n] == "count"]
    # a column named like a weight wins; then the only other number (messages, minutes...);
    # then count, which may be the one tareco added when merging repeated rows
    for pick in (named, [] if named else others, counts):
        if pick:
            return pick[0] if len(pick) == 1 else None
    return None


def _labels_something(name):
    """Numbers that name or date things rather than measure a connection: ids, years, codes."""
    words = re.sub(r"([a-z])([A-Z])", r"\1_\2", str(name)).lower()
    return bool(set(re.split(r"[^a-z0-9]+", words)) & NOT_WEIGHT)


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value == value


def read_csv(path, nodes=None, *, directed=False, source=None, target=None, node_id=None):
    """Graph from a CSV of edges (and optionally a CSV of nodes).

    Source/target columns are guessed (``source``, ``from``, ``origem``...) and
    fall back to the first two columns; every other column becomes an attribute.
    """
    from .graph import Graph
    return Graph(_read_table(path), directed=directed, nodes=nodes, source=source,
                 target=target, node_id=node_id)


def read_json(path):
    """Graph from a node-link JSON file (the format ``to_json`` writes)."""
    from .graph import Graph
    return Graph(path)


# --------------------------------------------------------------------- readers

def _resolve(obj):
    if isinstance(obj, (str, os.PathLike)):
        return _read_path(os.fspath(obj))
    return obj


def _read_path(path):
    if not os.path.exists(path):
        raise TarecoError(f"file not found: {path}")
    ext = os.path.splitext(path)[1].lower()
    if ext in (".xlsx", ".xlsm"):
        from .excel import read_excel
        return read_excel(path)
    if ext == ".xls":
        raise TarecoError(f"{path} is an old .xls file; save it as .xlsx (or CSV) and try again")
    if ext == ".json":
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    if ext in (".edges", ".edgelist"):
        return _read_edgelist(path)
    return _read_table(path)


def _read_table(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        sample = f.read(8192)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        except csv.Error:
            dialect = csv.excel
        reader = csv.DictReader(f, dialect=dialect)
        rows = []
        for row in reader:
            rows.append({(k or "").strip(): _parse_value(v) for k, v in row.items() if k is not None})
        return rows


def _read_edgelist(path):
    edges = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            parts = line.split("#", 1)[0].split()
            if len(parts) >= 2:
                edges.append(tuple(_parse_value(p) for p in parts[:3]))
    return edges


def _parse_value(text):
    if text is None:
        return None
    text = text.strip()
    if text == "":
        return None
    low = text.lower()
    if low in ("true", "false"):
        return low == "true"
    for cast in (int, float):
        try:
            return cast(text)
        except ValueError:
            pass
    if DECIMAL_COMMA.match(text):  # 1,5 as written in Brazil and most of Europe
        return float(text.replace(",", "."))
    return text


def _infer_directed(data):
    from .graph import Graph
    if isinstance(data, Graph):
        return data.directed
    if _is_networkx(data):
        return bool(data.is_directed())
    if isinstance(data, dict) and _is_node_link(data):
        return bool(data.get("directed", False))
    return False


def _has(obj, *names):
    """Real attributes only. Spark Connect DataFrames answer *any* attribute with a
    Column (``df.is_directed`` is a column named "is_directed"), so plain
    ``hasattr`` would mistake them for anything."""
    own = getattr(obj, "__dict__", {})
    kind = dir(type(obj))
    return all(name in kind or name in own for name in names)


def _is_networkx(obj):
    return _has(obj, "is_directed", "adj", "nodes")


def _is_dataframe(obj):
    return _has(obj, "columns", "to_dict", "iloc")


def _is_spark(obj):
    return _has(obj, "toLocalIterator", "schema", "columns")


def _is_polars(obj):
    return _has(obj, "iter_rows", "columns", "schema")


def _tabular(obj, max_rows):
    """``(columns, rows)`` for Spark, polars and pandas DataFrames; ``None`` otherwise."""
    if _is_spark(obj):
        return list(obj.columns), _spark_rows(obj, max_rows)
    if _is_polars(obj):
        return list(obj.columns), obj.iter_rows(named=True)
    if _is_dataframe(obj):
        return list(obj.columns), obj.to_dict("records")
    return None


def _spark_rows(df, max_rows):
    # toLocalIterator brings one partition at a time to the driver, not the whole table
    rows = df.limit(max_rows + 1) if max_rows is not None else df
    for i, row in enumerate(rows.toLocalIterator()):
        if max_rows is not None and i == max_rows:
            raise TarecoError(
                f"the Spark DataFrame has more than {max_rows:,} rows. Aggregate or filter it in "
                f"Spark first (groupBy source/target, a date range, a minimum weight...), or pass "
                f"max_rows=None to load everything into the driver")
        yield _row_dict(row)


def iter_table(data, max_rows=MAX_ROWS):
    """``(columns, rows)`` for anything tabular: files, DataFrames, Spark, records or tuples."""
    data = _resolve(data)
    table = _tabular(data, max_rows)
    if table is not None:
        return table
    if isinstance(data, (str, bytes, dict)):
        raise TarecoError("expected a table: a file, a DataFrame or a list of rows")
    try:
        items = [x for x in data if x is not None]
    except TypeError:
        raise TarecoError(f"cannot read a table from {type(data).__name__}") from None
    if not items:
        return [], []
    first = items[0]
    if hasattr(first, "asDict"):
        rows = [_row_dict(r) for r in items]
    elif isinstance(first, dict):
        rows = items
    elif isinstance(first, (tuple, list)):
        rows = [dict(enumerate(r)) for r in items]
    else:
        raise TarecoError("expected rows as dicts or tuples")
    return list(dict.fromkeys(k for r in rows for k in r)), rows


def _row_dict(row):
    return {k: _plain(v) for k, v in row.asDict(recursive=True).items()}


def _plain(value):
    # Spark returns DECIMAL columns as Decimal, which would not count as a number elsewhere
    return float(value) if isinstance(value, Decimal) else value


def _is_node_link(d):
    return any(isinstance(d.get(k), list) for k in ("nodes", "edges", "links"))


def _missing(value):
    if value is None:
        return True
    try:
        return bool(value != value)  # NaN
    except (TypeError, ValueError):
        return True  # pandas.NA


def _clean(record, skip=()):
    return {k: v for k, v in record.items() if k not in skip and not _missing(v)}


def _add_data(g, data, source, target, node_id, max_rows, options=None):
    from .graph import Graph
    options = {k: v for k, v in (options or {}).items() if v is not None}
    asked = [k for k in options if k != "directed"]

    def refuse():
        if asked:
            raise TarecoError(f"{', '.join(k + '=' for k in asked)} work with tables: a CSV or Excel "
                              f"file, a DataFrame or rows as dicts")

    table = _tabular(data, max_rows)
    if table is not None:
        _add_edge_records(g, table[1], source, target, table[0], **options)
    elif isinstance(data, Graph):
        refuse()
        for n, d in data.nodes.items():
            g._add_node(n, dict(d))
        for u, v, d in data._edge_triples():
            g._add_edge(u, v, dict(d))
            if g.directed and not data.directed:
                g._add_edge(v, u, dict(d))
        g.attrs = {**data.attrs, **g.attrs}
    elif _is_networkx(data):
        refuse()
        for n, d in data.nodes(data=True):
            g._add_node(n, dict(d))
        for u, v, d in data.edges(data=True):
            g._add_edge(u, v, dict(d))
    elif isinstance(data, dict):
        refuse()
        if _is_node_link(data):
            if isinstance(data.get("attrs"), dict):
                g.attrs.update(data["attrs"])
            _add_nodes_from(g, data.get("nodes") or [], node_id)
            links = data.get("edges") if data.get("edges") is not None else data.get("links")
            _add_edge_records(g, links or [], source, target)
        else:
            _add_adjacency(g, data)
    elif isinstance(data, (str, bytes)):
        raise TarecoError(f"cannot read {data!r} as a graph")
    else:
        try:
            items = list(data)
        except TypeError:
            raise TarecoError(f"cannot read a graph from {type(data).__name__}") from None
        first = next((x for x in items if x is not None), None)
        if first is None:
            return
        if hasattr(first, "asDict"):  # Spark Rows from df.collect()
            _add_edge_records(g, [_row_dict(r) for r in items if r is not None], source, target, **options)
        elif isinstance(first, dict):
            _add_edge_records(g, items, source, target, **options)
        elif isinstance(first, (tuple, list)) and not _looks_like_node_pair(first):
            refuse()
            g.add_edges(items)
        else:
            refuse()
            g.add_nodes(items)


def _looks_like_node_pair(item):
    # ("id", {attrs}) is a node with attributes, not an edge
    return len(item) == 2 and isinstance(item[1], dict)


def _add_adjacency(g, adj):
    for u, nbrs in adj.items():
        g._add_node(u, {})
        if nbrs is None:
            continue
        if isinstance(nbrs, dict):
            for v, extra in nbrs.items():
                if isinstance(extra, dict):
                    g._add_edge(u, v, dict(extra))
                elif extra is None:
                    g._add_edge(u, v, {})
                else:
                    g._add_edge(u, v, {"weight": extra})
        elif isinstance(nbrs, (list, tuple, set, frozenset)):
            for v in nbrs:
                g._add_edge(u, v, {})
        else:
            g._add_edge(u, nbrs, {})


def _add_edge_records(g, records, source, target, columns=None, *, kind=None, keep=None, account=None,
                      counterparty=None, amount=None, source_kind=None, target_kind=None, directed=None,
                      skip=None):
    skip = _skip_set(skip)
    watch = _Watch()
    statement = account is not None or counterparty is not None
    plain = not statement and kind is None and keep is None and source_kind is None and target_kind is None
    if columns is None or not plain:
        records = [r for r in records if r]
        if columns is None:
            if not records:
                return
            columns = list(dict.fromkeys(k for r in records for k in r))
    if plain:
        s = _pick_column(columns, source, SOURCE_COLUMNS, "source")
        t = _pick_column(columns, target, TARGET_COLUMNS, "target", exclude=s)
        if directed and not g.directed:
            g._make_directed()
        merger = EdgeMerger(g)
        for r in records:
            u, v = r.get(s), r.get(t)
            if _missing(u) or (skip and (u in skip or v in skip)):
                continue
            if _missing(v):
                g._add_node(u, {})
            else:
                watch.see(u, v)
                merger.add(u, v, _clean(r, (s, t)))
        merger.finish()
        watch.finish()
        return

    kept = _kept_columns(keep, columns)
    if statement:
        if skip:
            records = [r for r in records if r.get(account) not in skip and r.get(counterparty) not in skip]
        links, kinds, amount = _statement_links(records, columns, account, counterparty, amount)
        directed = True if directed is None else directed
    else:
        s = _pick_column(columns, source, SOURCE_COLUMNS, "source")
        t = _pick_column(columns, target, TARGET_COLUMNS, "target", exclude=s)
        sk, tk = source_kind, target_kind
        if kind is not None and sk is None and tk is None:
            sk, tk = _column_kinds(s, t)
        prefix = _prefixes(g, records, [(sk, s), (tk, t)])
        links = []
        for r in records:
            u, v = r.get(s), r.get(t)
            if _missing(u) or _missing(v) or (skip and (u in skip or v in skip)):
                continue
            if prefix.get(sk):
                u = prefix[sk] + str(u)
            if prefix.get(tk):
                v = prefix[tk] + str(v)
            links.append((u, v, _clean(r, (s, t)), r, sk, tk))
        kinds = (sk, tk)
        if directed is None:
            known = g.attrs.get("link_kinds", {})
            if kind in known:
                directed = known[kind]["directed"]
            elif sk is not None and tk is not None and sk != tk:
                directed = False  # an account and its device, a customer and a product: no flow
            else:
                directed = g.directed
    if directed and not g.directed:
        g._make_directed()
    if kind is not None:
        g.attrs.setdefault("link_kinds", {})[kind] = {"directed": bool(directed)}
    if kinds != (None, None):
        g.attrs.setdefault("node_kinds", [])
        for k in kinds:
            if k is not None and k not in g.attrs["node_kinds"]:
                g.attrs["node_kinds"].append(k)
    if kept is not None:
        g.attrs["kept"] = True
    merger = EdgeMerger(g)
    for u, v, attrs, row, ku, kv in links:
        if kind is not None:
            attrs["kind"] = kind
        watch.see(u, v)
        merger.add(u, v, attrs)
        if ku is not None:
            g._nodes[u].setdefault("kind", ku)
        if kv is not None:
            g._nodes[v].setdefault("kind", kv)
        if kept is not None:
            g._events.append((u, v, kind, dict(row) if kept is True else {c: row.get(c) for c in kept}))
    merger.finish()
    watch.finish()
    if statement and "weight" not in g.attrs:
        g.attrs["weight"] = amount


def _skip_set(skip):
    if skip is None:
        return None
    return {skip} if isinstance(skip, (str, int, float)) else set(skip)


def _kept_columns(keep, columns):
    """None (keep nothing), True (every column) or the list of columns to keep for each row."""
    if keep is None or keep is False:
        return None
    if keep is True:
        return True
    wanted = [keep] if isinstance(keep, str) else list(keep)
    missing = [c for c in wanted if c not in columns]
    if missing:
        raise TarecoError(f"no column {missing[0]!r} to keep; columns are {columns}")
    return wanted


def _statement_links(records, columns, account, counterparty, amount):
    """A bank statement (one row per entry on an account, money out negative) as links.

    Money out goes from the account to the counterparty; money in, from the counterparty
    to the account. When the statements of both accounts are in the table, each transfer
    shows up twice (out on one, in on the other) and is kept once, from the side it left.
    """
    if account is None or counterparty is None:
        raise TarecoError("a statement needs both account= and counterparty=")
    for col, role in ((account, "account"), (counterparty, "counterparty")):
        if col not in columns:
            raise TarecoError(f"no column {col!r} for {role}; columns are {columns}")
    if amount is None:
        rest = [c for c in columns if c not in (account, counterparty)]
        amount = guess_weight(rest, lambda c: (r.get(c) for r in records))
        if amount is None:
            raise TarecoError(f"which column has the amount? pass amount=...; columns are {columns}")
    elif amount not in columns:
        raise TarecoError(f"no column {amount!r} for amount; columns are {columns}")
    owners = {r.get(account) for r in records if not _missing(r.get(account))}
    own, other = str(account), str(counterparty)
    links = []
    for r in records:
        a, c, x = r.get(account), r.get(counterparty), r.get(amount)
        if _missing(a) or _missing(c) or not _is_number(x) or x == 0:
            continue
        if x < 0:
            u, v = a, c
        elif c not in owners:
            u, v = c, a
        else:
            continue  # the counterparty's own statement has this transfer, as money out
        attrs = _clean(r, (account, counterparty))
        attrs[amount] = abs(x)
        links.append((u, v, attrs, r, own if u in owners else other, own if v in owners else other))
    return links, (own, other), amount


def _column_kinds(s, t):
    """Node kinds named after the columns ("account", "device"), unless they only name a role."""
    a, b = _stem(s), _stem(t)
    if a is not None and b is not None and a != b:
        common = 0
        for x, y in zip(a, b):
            if x != y:
                break
            common += 1
        if common >= 3:  # payer and payee, caller and callee: two roles of one kind of thing
            return None, None
    return a, b


def _stem(name):
    if not isinstance(name, str):
        return None
    text = name.strip().lower()
    for prefix in ("from_", "to_", "src_", "dst_", "source_", "target_"):
        if text.startswith(prefix):
            text = text[len(prefix):]
    for suffix in ("_id", "_a", "_b", "_1", "_2", "_from", "_to", "_src", "_dst", "_source", "_target"):
        if text.endswith(suffix):
            text = text[:-len(suffix)]
    return None if not text or text in ROLE_WORDS else text


def _prefixes(g, records, ends):
    """Ids that clash with nodes of another kind get a prefix for their kind, like "device:123"."""
    known = g.attrs.get("prefixes", {})
    out = {}
    here = {}
    for k, col in ends:
        if k is None:
            continue
        if k in known:
            out[k] = known[k]
            continue
        ids = {r.get(col) for r in records if not _missing(r.get(col))}
        clash = None
        for x in ids:
            have = g._nodes.get(x)
            other = have.get("kind") if have is not None else here.get(x)
            if other is not None and other != k:
                clash = (x, other)
                break
        if clash is not None and k not in out:
            if any(d.get("kind") == k for d in g._nodes.values()):
                raise TarecoError(f"{clash[0]!r} is both a {clash[1]} and a {k}; add a prefix to the "
                                  f"ids of one of them in the table")
            out[k] = f"{k}:"
            warnings.warn(f"ids like {clash[0]!r} name both {clash[1]} and {k} nodes; the {k} nodes are "
                          f"called like '{k}:{clash[0]}'", GuessWarning, stacklevel=6)
        if k not in out:
            for x in ids:
                here.setdefault(x, k)
    if out:
        g.attrs.setdefault("prefixes", {}).update(out)
    return out


def _kinds_of(d):
    """The link kinds of an edge's attributes, as a tuple."""
    k = d.get("kind")
    if k is None:
        return ()
    return tuple(k) if isinstance(k, (list, tuple)) else (k,)


class EdgeMerger:
    """Tables often repeat a pair (one row per transfer, per message). Repeats become one
    edge whose numeric columns are summed, with ``count`` saying how many rows it holds.
    A pair already linked by an earlier table is merged the same way, and two kinds of
    link between the same pair are both kept in its ``kind``."""

    def __init__(self, g):
        self.g = g
        self.rows = {}
        self.repeated = False

    def add(self, u, v, attrs):
        g = self.g
        d = g._succ[u].get(v) if u in g._succ else None
        if d is None:
            g._add_edge(u, v, attrs)
            d = g._succ[u][v]
            self.rows[id(d)] = [d, 1]
            return
        entry = self.rows.get(id(d))
        if entry is None:  # the edge came from an earlier table
            entry = self.rows[id(d)] = [d, d.get("count", 1)]
        self.repeated = True
        entry[1] += 1
        for k, value in attrs.items():
            if k == "kind":
                kinds = _kinds_of(d)
                if value not in kinds:
                    d["kind"] = tuple(sorted(kinds + (value,), key=str)) if kinds else value
            elif _is_number(value) and _is_number(d.get(k)) and not _labels_something(k):
                d[k] += value  # amounts add up; ids, years and dates keep the first value
            else:
                d.setdefault(k, value)

    def finish(self):
        if self.repeated:
            for d, n in self.rows.values():
                d["count"] = n
            for _, _, d in self.g._edge_triples():
                d.setdefault("count", 1)


def _add_nodes_from(g, nodes, node_id, max_rows=MAX_ROWS):
    table = _tabular(nodes, max_rows)
    if table is not None:
        nodes = list(table[1])
    if isinstance(nodes, dict):
        for n, d in nodes.items():
            g._add_node(n, _clean(d) if isinstance(d, dict) else {"value": d})
        return
    items = [x for x in nodes if x is not None]
    if items and hasattr(items[0], "asDict"):
        items = [_row_dict(r) for r in items]
    if items and isinstance(items[0], dict):
        columns = list(dict.fromkeys(k for r in items for k in r))
        key = _pick_column(columns, node_id, ID_COLUMNS, "node id")
        for r in items:
            if not _missing(r.get(key)):
                g._add_node(r[key], _clean(r, (key,)))
    else:
        g.add_nodes(items)


def _pick_column(columns, explicit, candidates, role, exclude=None):
    if explicit is not None:
        if explicit not in columns:
            raise TarecoError(f"no column {explicit!r} for {role}; columns are {columns}")
        return explicit
    lowered = {str(c).strip().lower(): c for c in columns if c != exclude}
    present = {str(c).strip().lower() for c in columns}
    for name in candidates:
        # short names only mean source/target as a pair: a lone "v" is more likely a value
        if name in PAIRED and PAIRED[name] not in present:
            continue
        if name in lowered:
            return lowered[name]
    free = [c for c in columns if c != exclude]
    if free:
        if isinstance(free[0], str) and role != "node id":  # node tables lead with the id by convention
            option = {"source": "source", "target": "target"}.get(role, "node_id")
            warnings.warn(f"no column looks like the {role}, so {free[0]!r} was used; pass "
                          f"{option}=... to choose another", GuessWarning, stacklevel=4)
        return free[0]
    raise TarecoError(f"cannot tell which column is the {role}; columns are {columns}")


# --------------------------------------------------------------------- writers

def to_dict(g):
    return {
        "directed": g.directed,
        "attrs": dict(g.attrs),
        "nodes": [{**d, "id": n} for n, d in g.nodes.items()],
        "edges": [{**d, "source": u, "target": v} for u, v, d in g._edge_triples()],
    }


def to_json(g, path=None, indent=2):
    text = json.dumps(to_dict(g), indent=indent, default=json_default, ensure_ascii=False)
    if path is None:
        return text
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return None


def json_default(value):
    if hasattr(value, "item"):  # numpy scalars
        return value.item()
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "isoformat"):  # dates and datetimes
        return value.isoformat()
    if isinstance(value, (set, frozenset, tuple)):
        return list(value)
    return str(value)


def to_csv(g, edges_path, nodes_path=None):
    edge_cols = list(dict.fromkeys(k for _, _, d in g._edge_triples() for k in d))
    with open(edges_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["source", "target"] + edge_cols)
        for u, v, d in g._edge_triples():
            w.writerow([u, v] + [d.get(c, "") for c in edge_cols])
    if nodes_path is not None:
        node_cols = list(dict.fromkeys(k for _, d in g.nodes.items() for k in d))
        with open(nodes_path, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["id"] + node_cols)
            for n, d in g.nodes.items():
                w.writerow([n] + [d.get(c, "") for c in node_cols])


def to_pandas(g, metrics=None):
    try:
        import pandas as pd
    except ImportError:
        raise TarecoError("to_pandas needs pandas: pip install pandas") from None
    from .metrics import edge_rows, node_rows
    nodes = pd.DataFrame(node_rows(g, metrics))
    edges = pd.DataFrame(edge_rows(g))
    if nodes.empty:
        nodes = pd.DataFrame(columns=["id"])
    if edges.empty:
        edges = pd.DataFrame(columns=["source", "target"])
    return nodes, edges


def to_networkx(g):
    try:
        import networkx as nx
    except ImportError:
        raise TarecoError("to_networkx needs networkx: pip install networkx") from None
    out = nx.DiGraph() if g.directed else nx.Graph()
    out.graph.update(g.attrs)
    out.add_nodes_from((n, dict(d)) for n, d in g.nodes.items())
    out.add_edges_from((u, v, dict(d)) for u, v, d in g._edge_triples())
    return out

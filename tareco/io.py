"""Reading graphs from whatever the user has, and writing them back out."""

import csv
import json
import os
import re
from decimal import Decimal

from .errors import TarecoError

SOURCE_COLUMNS = ("source", "from", "src", "origin", "origem", "de", "sender",
                  "start", "parent", "u", "node1")
TARGET_COLUMNS = ("target", "to", "dst", "destination", "dest", "destino", "para",
                  "receiver", "end", "child", "v", "node2")
ID_COLUMNS = ("id", "node", "name", "key", "label", "nome")
PAIRED = {"u": "v", "v": "u", "node1": "node2", "node2": "node1"}
DECIMAL_COMMA = re.compile(r"^-?\d+,\d+$")
MAX_ROWS = 1_000_000


def load_into(g, data, *, directed=None, nodes=None, source=None, target=None, node_id=None,
              max_rows=MAX_ROWS):
    data = _resolve(data)
    if directed is None:
        directed = _infer_directed(data)
    g._reset(bool(directed))
    if nodes is not None:
        _add_nodes_from(g, _resolve(nodes), node_id, max_rows)
    if data is not None:
        _add_data(g, data, source, target, node_id, max_rows)


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


def _is_networkx(obj):
    return hasattr(obj, "is_directed") and hasattr(obj, "adj") and hasattr(obj, "nodes")


def _is_dataframe(obj):
    return hasattr(obj, "columns") and hasattr(obj, "to_dict") and hasattr(obj, "iloc")


def _is_spark(obj):
    return hasattr(obj, "toLocalIterator") and hasattr(obj, "schema") and hasattr(obj, "columns")


def _is_polars(obj):
    return hasattr(obj, "iter_rows") and hasattr(obj, "columns") and hasattr(obj, "schema")


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


def _add_data(g, data, source, target, node_id, max_rows):
    from .graph import Graph
    table = _tabular(data, max_rows)
    if table is not None:
        _add_edge_records(g, table[1], source, target, table[0])
    elif isinstance(data, Graph):
        for n, d in data.nodes.items():
            g._add_node(n, dict(d))
        for u, v, d in data._edge_triples():
            g._add_edge(u, v, dict(d))
            if g.directed and not data.directed:
                g._add_edge(v, u, dict(d))
        g.attrs = {**data.attrs, **g.attrs}
    elif _is_networkx(data):
        for n, d in data.nodes(data=True):
            g._add_node(n, dict(d))
        for u, v, d in data.edges(data=True):
            g._add_edge(u, v, dict(d))
    elif isinstance(data, dict):
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
            _add_edge_records(g, [_row_dict(r) for r in items if r is not None], source, target)
        elif isinstance(first, dict):
            _add_edge_records(g, items, source, target)
        elif isinstance(first, (tuple, list)) and not _looks_like_node_pair(first):
            g.add_edges(items)
        else:
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


def _add_edge_records(g, records, source, target, columns=None):
    if columns is None:
        records = [r for r in records if r]
        if not records:
            return
        columns = list(dict.fromkeys(k for r in records for k in r))
    s = _pick_column(columns, source, SOURCE_COLUMNS, "source")
    t = _pick_column(columns, target, TARGET_COLUMNS, "target", exclude=s)
    for r in records:
        u, v = r.get(s), r.get(t)
        if _missing(u):
            continue
        if _missing(v):
            g._add_node(u, {})
        else:
            g._add_edge(u, v, _clean(r, (s, t)))


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

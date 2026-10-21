"""The part of a huge edge table around a few nodes, without loading the table.

Start from the nodes you care about and expand hop by hop. With a Spark
DataFrame every hop is a query that runs in the cluster; only the matching
edges come back to Python.
"""

from .errors import TarecoError
from .graph import Graph
from .io import (MAX_ROWS, SOURCE_COLUMNS, TARGET_COLUMNS, _is_dataframe, _is_spark, _missing,
                 _pick_column, _spark_rows, iter_table)

JOIN_ABOVE = 2_000   # Spark: match more nodes than this with a broadcast join instead of isin


def neighborhood(data, start, hops=2, source=None, target=None, directed=False, direction="both",
                 max_nodes=5_000, max_rows=MAX_ROWS):
    """Everything within ``hops`` steps of ``start``, read from an edge table.

    data        Spark DataFrame (queries run in Spark), pandas DataFrame, CSV
                path, or rows.
    start       one node or a list of nodes.
    direction   "both", "out" (follow edges forward) or "in" (backward).
    max_nodes   stop growing at this many nodes; the last hop keeps its most
                connected nodes and the graph is marked ``attrs["truncated"]``.

    Each node gets a ``hop`` attribute (0 for the start), handy for
    ``show(color="hop")``.
    """
    if direction not in ("both", "out", "in"):
        raise TarecoError('direction must be "both", "out" or "in"')
    starts = list(start) if isinstance(start, (list, tuple, set, frozenset)) else [start]
    if not starts:
        raise TarecoError("start needs at least one node")
    fetch, columns = _fetcher(data, max_rows)
    s = _pick_column(columns, source, SOURCE_COLUMNS, "source")
    t = _pick_column(columns, target, TARGET_COLUMNS, "target", exclude=s)

    hop_of = {n: 0 for n in starts}
    edges = {}
    frontier = set(starts)
    truncated = False
    for h in range(1, hops + 1):
        if not frontier:
            break
        touching = {}
        for row in fetch(frontier, s, t, direction):
            u, v = row.get(s), row.get(t)
            if _missing(u) or _missing(v):
                continue
            edges[(u, v)] = row
            for node in (u, v):
                if node not in hop_of:
                    touching[node] = touching.get(node, 0) + 1
        room = max_nodes - len(hop_of)
        if len(touching) > room:
            truncated = True
            touching = dict(sorted(touching.items(), key=lambda kv: -kv[1])[:max(0, room)])
        for node in touching:
            hop_of[node] = h
        frontier = set(touching)
        if truncated:
            break

    g = Graph(directed=directed)
    for node, h in sorted(hop_of.items(), key=lambda kv: kv[1]):
        g._add_node(node, {"hop": h})
    for (u, v), row in edges.items():
        if u in hop_of and v in hop_of:
            g._add_edge(u, v, {k: val for k, val in row.items() if k not in (s, t) and not _missing(val)})
    g.attrs.update({"start": starts, "hops": hops, "truncated": truncated})
    return g


def _fetcher(data, max_rows):
    """``(fetch(nodes, s, t, direction) -> rows, columns)`` for the kind of table given."""
    if _is_spark(data):
        return _spark_fetch(data, max_rows), list(data.columns)
    if _is_dataframe(data):
        def fetch(nodes, s, t, direction):
            mask = None
            if direction in ("both", "out"):
                mask = data[s].isin(list(nodes))
            if direction in ("both", "in"):
                other = data[t].isin(list(nodes))
                mask = other if mask is None else (mask | other)
            return data[mask].to_dict("records")
        return fetch, list(data.columns)
    columns, rows = iter_table(data, max_rows)
    rows = list(rows)

    def fetch(nodes, s, t, direction):
        return [r for r in rows
                if (direction != "in" and r.get(s) in nodes) or (direction != "out" and r.get(t) in nodes)]
    return fetch, columns


def _spark_fetch(df, max_rows):
    def fetch(nodes, s, t, direction):
        from pyspark.sql import functions as F
        values = list(nodes)
        sides = [c for c, d in ((s, "out"), (t, "in")) if direction in ("both", d)]
        if len(values) <= JOIN_ABOVE:
            cond = None
            for c in sides:
                here = F.col(c).isin(values)
                cond = here if cond is None else (cond | here)
            part = df.filter(cond)
        else:
            ids = df.sparkSession.createDataFrame([(v,) for v in values], ["__tareco_node"])
            parts = [df.join(F.broadcast(ids), df[c] == ids["__tareco_node"], "left_semi") for c in sides]
            part = parts[0] if len(parts) == 1 else parts[0].unionByName(parts[1])
        return _spark_rows(part, max_rows)
    return fetch


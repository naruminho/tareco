"""Node metrics by name, and tables of nodes with them, for pandas or Spark."""

from .errors import TarecoError

NAMES = ("degree", "in_degree", "out_degree", "pagerank", "betweenness", "closeness", "clustering",
         "core", "community", "component")


def compute(g, name):
    """``{node: value}`` for a metric name."""
    if name == "degree":
        return g.degree()
    if name == "in_degree":
        return g.in_degree()
    if name == "out_degree":
        return g.out_degree()
    if name == "pagerank":
        return g.pagerank()
    if name == "betweenness":
        return g.betweenness()
    if name == "closeness":
        return g.closeness()
    if name == "clustering":
        return g.clustering()
    if name == "core":
        return g.core_number()
    if name in ("community", "component"):
        groups = g.communities() if name == "community" else g.components()
        return {n: i + 1 for i, members in enumerate(groups) for n in members}
    raise TarecoError(f"unknown metric {name!r}; choose from {NAMES}")


def node_rows(g, metrics=None):
    """One dict per node: ``id``, its attributes and the requested metrics."""
    names = [metrics] if isinstance(metrics, str) else list(metrics or [])
    values = {name: compute(g, name) for name in names}
    rows = []
    for n, attrs in g.nodes.items():
        row = {"id": n, **attrs}
        for name in names:
            row[name] = values[name][n]
        rows.append(row)
    return rows


def edge_rows(g):
    return [{"source": u, "target": v, **d} for u, v, d in g._edge_triples()]


def to_spark(g, spark, metrics=None):
    """``(nodes, edges)`` as Spark DataFrames, ready to join with other tables or save."""
    nodes = node_rows(g, metrics)
    edges = edge_rows(g)
    ids = {type(n) for n in g}
    mixed_ids = len(ids) > 1
    if mixed_ids:  # Spark columns need one type; ids like 1 and "a" become text
        for row in nodes:
            row["id"] = str(row["id"])
        for row in edges:
            row["source"], row["target"] = str(row["source"]), str(row["target"])
    return (_spark_frame(spark, nodes, ["id"]),
            _spark_frame(spark, edges, ["source", "target"]))


def _spark_frame(spark, rows, keys):
    columns = list(dict.fromkeys(k for r in rows for k in r)) or keys
    kinds = {}
    for c in columns:
        seen = {type(r.get(c)) for r in rows if r.get(c) is not None}
        if not seen:
            kinds[c] = None
        elif seen <= {int, float}:
            kinds[c] = float if float in seen else int
        elif len(seen) == 1:
            kinds[c] = seen.pop()
        else:
            kinds[c] = str
    columns = [c for c in columns if kinds[c] is not None or c in keys]
    if not rows:
        return spark.createDataFrame([], ", ".join(f"`{c}` string" for c in columns))

    def cast(value, kind):
        if value is None or kind is None:
            return None
        if kind is str and not isinstance(value, str):
            return str(value)
        if kind is float:
            return float(value)
        if isinstance(value, (list, tuple, set, frozenset, dict)):
            return str(value)
        return value

    data = [tuple(cast(r.get(c), kinds[c]) for c in columns) for r in rows]
    return spark.createDataFrame(data, columns)

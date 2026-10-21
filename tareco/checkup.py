"""Check that tareco works where it runs: notebook, output limits, Spark (classic or Connect)."""

import platform
import sys
import time
import traceback


class Check:
    __slots__ = ("name", "status", "detail", "seconds")

    def __init__(self, name, status, detail, seconds):
        self.name = name
        self.status = status      # "ok", "fail" or "skip"
        self.detail = detail
        self.seconds = seconds


class Report(list):
    """The result of ``doctor()``: one Check per line. ``report.ok`` is True when nothing failed."""

    @property
    def ok(self):
        return all(c.status != "fail" for c in self)

    @property
    def failures(self):
        return [c for c in self if c.status == "fail"]

    def __repr__(self):
        width = max((len(c.name) for c in self), default=10)
        lines = [f"{c.status.upper():<5} {c.name:<{width}}  {c.detail}" for c in self]
        verdict = "all good" if self.ok else f"{len(self.failures)} problem(s)"
        return "\n".join(lines + [f"tareco doctor: {verdict}"])

    def _repr_markdown_(self):
        rows = [f"| {c.status.upper()} | {c.name} | {c.detail.replace('|', '/')} |" for c in self]
        verdict = "all good" if self.ok else f"{len(self.failures)} problem(s)"
        return "\n".join([f"**tareco doctor: {verdict}**", "", "| | check | detail |", "|---|---|---|"] + rows)


def doctor(spark=None, quick=False):
    """Run every check that can fail in a new environment and report each one.

    Pass the notebook's ``spark`` session to check reading from Spark,
    neighborhoods, exports and timelines there (classic Spark or Spark Connect,
    as on Databricks serverless). Nothing is written outside memory and the
    temporary folder. ``quick`` skips the bigger graphs.
    """
    from . import __version__
    report = Report()

    def run(name, fn):
        start = time.perf_counter()
        try:
            out = fn()
            status, detail = ("skip", out[5:]) if isinstance(out, str) and out.startswith("skip:") else ("ok", out or "")
        except Exception as e:  # report everything, keep going
            status = "fail"
            detail = f"{type(e).__name__}: {e}"
            last = traceback.extract_tb(e.__traceback__)[-1:]
            if last:
                detail += f" ({last[0].filename.split('tareco')[-1]}:{last[0].lineno})"
        report.append(Check(name, status, str(detail), time.perf_counter() - start))

    run("environment", lambda: _environment(__version__, spark))
    run("algorithms", _algorithms)
    run("explain", _explain)
    run("canvas page", _canvas_page)
    run("webgl page", lambda: _webgl_page(quick))
    run("notebook output", lambda: _notebook_output(quick))
    run("timeline", _timeline_rows)
    run("report", _report)
    if spark is None:
        report.append(Check("spark", "skip", "pass doctor(spark) to check Spark", 0.0))
        return report
    run("spark: flavor", lambda: _spark_flavor(spark))
    run("spark: read edges", lambda: _spark_read(spark))
    run("spark: row limit", lambda: _spark_limit(spark))
    run("spark: neighborhood (isin)", lambda: _spark_neighborhood(spark, join=False))
    run("spark: neighborhood (join)", lambda: _spark_neighborhood(spark, join=True))
    run("spark: to_spark", lambda: _spark_export(spark))
    run("spark: timeline", lambda: _spark_timeline(spark))
    run("spark: project", lambda: _spark_project(spark))
    return report


# ----------------------------------------------------------------- checks

def _environment(version, spark):
    from .viz import _in_notebook, _on_databricks, default_budget_mb
    import os
    where = ("Databricks " + os.environ.get("DATABRICKS_RUNTIME_VERSION", "")) if _on_databricks() else (
        "notebook" if _in_notebook() else "script")
    return (f"tareco {version}, Python {platform.python_version()}, {where}, "
            f"notebook output budget {default_budget_mb()} MB")


def _algorithms():
    from .generators import community_graph
    g = community_graph([30, 30, 30], p_in=0.3, p_out=0.01, seed=1)
    comms = g.communities()
    assert len(comms) == 3, f"expected 3 communities, got {len(comms)}"
    assert abs(sum(g.pagerank().values()) - 1) < 1e-6
    assert g.shortest_path(0, 89)
    return f"{len(g)} nodes, {g.edge_count} edges, 3 communities found"


def _explain():
    from .generators import community_graph
    g = community_graph([20, 20], p_in=0.4, p_out=0.02, seed=2)
    for n, attrs in g.nodes.items():
        attrs["side"] = "left" if attrs["group"] == 0 else "right"
    text = str(g.explain(lang="pt"))
    assert "Formam-se 2 grupos" in text and "side: left" in text, text[:200]
    return "plain-language findings in Portuguese"


def _canvas_page():
    from .generators import path_graph
    page = path_graph(20).to_html()
    assert "ForceGraph" in page and all(ord(c) < 128 for c in page)
    return f"{len(page) / 1e6:.2f} MB, ASCII only"


def _webgl_page(quick):
    from .generators import scale_free_graph
    g = scale_free_graph(3000 if quick else 20000, 3, seed=1)
    page = g.to_html()
    assert '"renderer":"webgl"' in page and all(ord(c) < 128 for c in page)
    return f"{len(g):,} nodes, {len(page) / 1e6:.1f} MB, ASCII only"


def _notebook_output(quick):
    from .generators import scale_free_graph
    from .viz import default_budget_mb, notebook_html
    budget = default_budget_mb()
    g = scale_free_graph(5000 if quick else 60000, 3, seed=1)
    html = notebook_html(g)
    size = len(html.encode()) / 1e6
    assert size <= budget, f"{size:.1f} MB is over the {budget} MB budget"
    return f"{len(g):,}-node graph fits in {size:.1f} MB (budget {budget} MB)"


def _timeline_rows():
    from .temporal import timeline
    rows = [(f"n{i % 7}", f"n{(i * 3) % 11}", f"2026-{1 + i % 6:02d}-1{i % 9}") for i in range(200)]
    tl = timeline(rows, time=2)
    page = tl.to_html()
    assert "tarecoTimebar" in page
    return f"{len(tl)} {tl.freq} periods"


def _report():
    from .generators import community_graph
    page = community_graph([15, 15], seed=3).report()
    assert "<iframe srcdoc=" in page and all(ord(c) < 128 for c in page)
    return f"{len(page) / 1e6:.2f} MB, ASCII only"


def _spark_flavor(spark):
    kind = type(spark).__module__
    flavor = "Spark Connect" if ".connect" in kind else "classic Spark"
    return f"{flavor}, Spark {getattr(spark, 'version', '?')}"


def _edges(spark):
    rows = [(f"n{i}", f"n{(i * 7 + 1) % 60}", float(i % 9 + 1)) for i in range(120)]
    rows += [("n0", "hub", 1.0), ("n1", "hub", 2.0)]
    return spark.createDataFrame(rows, "origem string, destino string, valor double")


def _spark_read(spark):
    from .graph import Graph
    g = Graph(_edges(spark))
    assert g.edge_count >= 100 and "hub" in g, g
    assert set(g.edges["n0", "hub"]) == {"valor"}
    return f"{len(g)} nodes, {g.edge_count} edges, columns guessed (origem/destino)"


def _spark_limit(spark):
    from .errors import TarecoError
    from .graph import Graph
    try:
        Graph(_edges(spark), max_rows=10)
    except TarecoError:
        return "tables over max_rows are refused with a hint"
    raise AssertionError("max_rows was not enforced")


def _spark_neighborhood(spark, join):
    from . import around
    old = around.JOIN_ABOVE
    around.JOIN_ABOVE = 0 if join else 10_000
    try:
        g = around.neighborhood(_edges(spark), start="hub", hops=2)
    finally:
        around.JOIN_ABOVE = old
    hops = {g.nodes[n]["hop"] for n in g}
    assert hops == {0, 1, 2}, hops
    return f"{len(g)} nodes within 2 hops of 'hub'"


def _spark_export(spark):
    from .graph import Graph
    g = Graph([("a", "b", 1.5), ("b", "c", 2.0)], nodes={"a": {"team": "x"}})
    nodes, edges = g.to_spark(spark, metrics=["degree", "community"])
    assert nodes.count() == 3 and edges.count() == 2
    assert {"id", "team", "degree", "community"} <= set(nodes.columns)
    return "nodes and edges written back as Spark DataFrames"


def _spark_timeline(spark):
    from .temporal import timeline
    df = spark.createDataFrame(
        [("a", "b", "2026-01-05 10:00:00"), ("b", "c", "2026-02-07 11:30:00"), ("c", "a", "2026-03-09 09:15:00")],
        "src string, dst string, at string")
    try:
        from pyspark.sql import functions as F
        df = df.withColumn("at", F.to_timestamp("at"))
    except ImportError:
        pass
    tl = timeline(df, time="at", freq="month")
    assert tl.periods == ["2026-01", "2026-02", "2026-03"], tl.periods
    return "Spark timestamps read as times, 3 monthly periods"


def _spark_project(spark):
    from .bipartite import project
    df = spark.createDataFrame([("ana", "x"), ("bia", "x"), ("bia", "y"), ("caio", "y")],
                               "person string, item string")
    g = project(df, nodes="person", via="item")
    assert g.has_edge("ana", "bia") and g.has_edge("bia", "caio")
    return "two-sided table projected"


def main():
    print(doctor(quick="--quick" in sys.argv))


if __name__ == "__main__":
    main()

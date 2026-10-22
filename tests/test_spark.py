"""Spark support. A fake DataFrame mirrors the pyspark API; the real one runs where Spark is installed."""

import datetime
import shutil
from decimal import Decimal

import pytest

import tareco as tc
from tareco import TarecoError


class Row(tuple):
    """Like pyspark.sql.Row: a tuple that knows its field names."""

    def __new__(cls, **fields):
        row = super().__new__(cls, fields.values())
        row._fields = list(fields)
        return row

    def asDict(self, recursive=False):
        return {k: (v.asDict(recursive) if recursive and isinstance(v, Row) else v)
                for k, v in zip(self._fields, self)}


class FakeSparkDataFrame:
    def __init__(self, rows):
        self.rows = rows
        self.columns = list(rows[0]._fields) if rows else []
        self.schema = object()
        self.limits = []
        self.streamed = False

    def limit(self, n):
        self.limits.append(n)
        out = FakeSparkDataFrame(self.rows[:n])
        out.parent = self
        return out

    def toLocalIterator(self):
        getattr(self, "parent", self).streamed = True
        return iter(self.rows)

    def collect(self):
        raise AssertionError("tareco must stream, not collect the whole table")


def edges_df():
    return FakeSparkDataFrame([
        Row(src="ana", dst="bia", amount=Decimal("10.50"), day=datetime.date(2026, 1, 2)),
        Row(src="bia", dst="caio", amount=Decimal("3"), day=datetime.date(2026, 1, 3)),
        Row(src="caio", dst=None, amount=None, day=None),
    ])


def test_spark_dataframe_edges_are_streamed():
    df = edges_df()
    g = tc.Graph(df, directed=True)
    assert df.streamed and df.limits == [1_000_001]
    assert g.edges["ana", "bia"] == {"amount": 10.5, "day": datetime.date(2026, 1, 2)}
    assert isinstance(g.edges["ana", "bia"]["amount"], float)
    assert "caio" in g and g.edge_count == 2


def test_spark_dataframe_nodes_and_explicit_columns():
    nodes = FakeSparkDataFrame([Row(name="ana", team="x"), Row(name="bia", team="y")])
    g = tc.Graph(edges_df(), nodes=nodes, source="dst", target="src")
    assert g.nodes["ana"] == {"team": "x"}
    assert g.has_edge("bia", "ana")


def test_spark_row_limit():
    rows = [Row(a=i, b=i + 1) for i in range(10)]
    with pytest.raises(TarecoError, match="more than 5 rows"):
        tc.Graph(FakeSparkDataFrame(rows), max_rows=5)
    df = FakeSparkDataFrame(rows)
    assert tc.Graph(df, max_rows=None).edge_count == 10 and df.limits == []


def test_collected_rows_and_nested_structs():
    rows = [Row(source="a", target="b", meta=Row(kind="loan", value=Decimal("2.5")))]
    g = tc.Graph(rows)
    assert g.edges["a", "b"] == {"meta": {"kind": "loan", "value": Decimal("2.5")}}
    nodes = [Row(id="a", score=Decimal("1.25"))]
    assert tc.Graph([("a", "b")], nodes=nodes).nodes["a"] == {"score": 1.25}


def test_spark_values_survive_the_view_and_json():
    g = tc.Graph(edges_df())
    page = g.to_html(edge_width="amount")
    assert "2026-01-02" in page
    assert '"amount": 10.5' in g.to_json()


def test_show_accepts_spark(monkeypatch):
    opened = []
    monkeypatch.setattr("webbrowser.open", lambda url: opened.append(url) or True)
    tc.show(edges_df(), max_rows=100)
    assert len(opened) == 1


def test_polars_dataframe():
    pl = pytest.importorskip("polars")
    df = pl.DataFrame({"from": ["a", "b"], "to": ["b", "c"], "w": [1.0, None]})
    g = tc.Graph(df, nodes=pl.DataFrame({"id": ["a"], "kind": ["x"]}))
    assert g.edges["a", "b"] == {"w": 1.0} and g.edges["b", "c"] == {}
    assert g.nodes["a"] == {"kind": "x"}


@pytest.fixture(scope="module")
def spark():
    pyspark = pytest.importorskip("pyspark")
    if not shutil.which("java") and not __import__("os").environ.get("JAVA_HOME"):
        pytest.skip("Spark needs Java")
    session = pyspark.sql.SparkSession.builder.master("local[1]").appName("tareco").getOrCreate()
    yield session
    session.stop()


def test_real_spark(spark):
    df = spark.createDataFrame(
        [("ana", "bia", 2.0), ("bia", "caio", 1.0), ("caio", "ana", 4.0)],
        "origem string, destino string, valor double")
    g = tc.Graph(df)
    assert g.edge_count == 3 and g.edges["ana", "bia"] == {"valor": 2.0}
    assert g.shortest_path("ana", "caio") == ["ana", "caio"]
    with pytest.raises(TarecoError):
        tc.Graph(df, max_rows=2)


def test_real_spark_neighborhood_and_export(spark, monkeypatch):
    from tareco import around as nb
    df = spark.createDataFrame(
        [("a", "b", 1.0), ("b", "c", 2.0), ("c", "d", 3.0), ("x", "a", 4.0)],
        "src string, dst string, amount double")
    g = tc.neighborhood(df, start="a", hops=2)
    assert {n: g.nodes[n]["hop"] for n in g} == {"a": 0, "b": 1, "x": 1, "c": 2}
    monkeypatch.setattr(nb, "JOIN_ABOVE", 0)  # force the broadcast-join path
    joined = tc.neighborhood(df, start="a", hops=2, direction="out", directed=True)
    assert set(joined) == {"a", "b", "c"}
    nodes, edges = g.to_spark(spark, metrics=["degree", "community"])
    assert nodes.count() == 4 and edges.count() == 3
    assert set(nodes.columns) >= {"id", "hop", "degree", "community"}


def test_real_spark_doctor(spark):
    report = tc.doctor(spark, quick=True)
    assert report.ok, repr(report)
    assert next(c for c in report if c.name == "spark: flavor").detail.startswith("classic Spark")


class ConnectLikeDataFrame(FakeSparkDataFrame):
    """Spark Connect answers any unknown attribute with a Column object."""

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return ("Column", name)


def test_spark_connect_dataframes_are_not_mistaken_for_other_things():
    rows = [Row(origem="a", destino="b"), Row(origem="b", destino="c")]
    df = ConnectLikeDataFrame(rows)
    assert hasattr(df, "is_directed") and hasattr(df, "iter_rows")  # the trap
    g = tc.Graph(df)  # must not treat it as a networkx graph or a polars frame
    assert not g.directed and g.edge_count == 2
    assert tc.project(ConnectLikeDataFrame([Row(p="x", i=1), Row(p="y", i=1)])).has_edge("x", "y")


def test_real_spark_statements_and_records(spark, monkeypatch):
    from tareco import tracing
    df = spark.createDataFrame(
        [("T1", "a1", "a2", -100.0), ("T2", "a2", "a1", 100.0), ("T3", "a2", "SHOP", -40.0)],
        "tid string, account string, counterparty string, amount double")
    g = tc.Graph(df, account="account", counterparty="counterparty", keep=True)
    assert set(g.edges) == {("a1", "a2"), ("a2", "SHOP")} and g.rows("SHOP").column("tid") == ["T3"]
    found = tc.records(df, ["a1"], columns=["account"])
    assert "DataFrame" in type(found).__name__ and [r["tid"] for r in found.collect()] == ["T1"]
    monkeypatch.setattr(tracing, "JOIN_ABOVE", 0)  # the broadcast-join path
    both = tc.records(df, ["SHOP", "a1"], columns=["account", "counterparty"])
    assert sorted(r["tid"] for r in both.collect()) == ["T1", "T2", "T3"]


def test_review_to_spark(spark):
    rows = [{"tid": f"T{k}", "from": "p", "to": f"q{k % 2}", "amount": 9500 + k, "date": f"2026-01-0{k + 1}"}
            for k in range(6)]
    rows += [{"tid": f"S{k}", "from": f"p{k}", "to": "shop", "amount": 20 + k, "date": "2026-01-01"} for k in range(30)]
    g = tc.Graph(rows, directed=True, keep=True)
    df = g.review(limit=10_000).to_spark(spark)
    first = df.collect()[0]
    assert first["node"] == "p" and first["score"] >= 3 and "T0" in first["ids"]


def test_big_algorithms_in_spark(spark):
    rows = [("a", "b", 1.0), ("b", "c", 1.0), ("c", "a", 1.0), ("x", "y", 2.0)]
    df = spark.createDataFrame(rows, "src string, dst string, w double")
    comps = {r["node"]: r["component"] for r in tc.big.components(df).collect()}
    assert comps["a"] == comps["b"] == comps["c"] == 1 and comps["x"] == comps["y"] == 2
    deg = {r["node"]: r for r in tc.big.degrees(df, weight="w").collect()}
    assert deg["a"]["out_links"] == 1 and deg["a"]["links"] == 2 and deg["x"]["out_weight"] == 2.0
    ranks = {r["node"]: r["pagerank"] for r in tc.big.pagerank(df, iterations=60).collect()}
    local = tc.Graph([(a, b) for a, b, _ in rows], directed=True).pagerank(weight=None)
    assert all(abs(ranks[k] - local[k]) < 1e-3 for k in local), (ranks, local)
    groups = {r["node"]: r["community"] for r in tc.big.communities(df).collect()}
    assert groups["a"] == groups["b"] == groups["c"] and groups["x"] == groups["y"] != groups["a"]
    st = spark.createDataFrame(
        [("T1", "a1", "a2", -100.0), ("T2", "a2", "a1", 100.0), ("T3", "a2", "SHOP", -40.0), ("T4", "a1", "BOSS", 3000.0)],
        "tid string, account string, counterparty string, amount double")
    edges = tc.big.statement_edges(st, "account", "counterparty", "amount")
    got = sorted((r["source"], r["target"], r["amount"]) for r in edges.collect())
    assert got == [("BOSS", "a1", 3000.0), ("a1", "a2", 100.0), ("a2", "SHOP", 40.0)]
    near = tc.neighborhood(edges, start="a1", hops=1)
    assert set(near) == {"a1", "a2", "BOSS"}

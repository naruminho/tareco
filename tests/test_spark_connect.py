"""Spark Connect, the protocol behind Databricks serverless and shared clusters.

Runs against a local Spark Connect server started by pyspark itself. Needs
``pip install "pyspark[connect]"`` and Java; skipped otherwise. Run it in its
own pytest process: a classic Spark session in the same process gets in the way.
"""

import os
import shutil

import pytest

import tareco as tc


@pytest.fixture(scope="module")
def spark():
    pytest.importorskip("pyspark.sql.connect.session")
    if not shutil.which("java") and not os.environ.get("JAVA_HOME"):
        pytest.skip("Spark needs Java")
    from pyspark.sql import SparkSession
    try:
        session = SparkSession.builder.remote("local[1]").getOrCreate()
    except Exception as e:  # missing connect extras (grpcio, pyarrow...)
        pytest.skip(f"cannot start a local Spark Connect server: {e}")
    yield session
    session.stop()


def test_it_really_is_spark_connect(spark):
    df = spark.createDataFrame([("a", "b")], "src string, dst string")
    assert "connect" in type(df).__module__


def test_doctor_on_spark_connect(spark):
    report = tc.doctor(spark, quick=True)
    assert report.ok, repr(report)
    flavor = next(c for c in report if c.name == "spark: flavor")
    assert flavor.detail.startswith("Spark Connect")


def test_graph_neighborhood_and_export(spark, monkeypatch):
    from tareco import around
    df = spark.createDataFrame(
        [("a", "b", 1.0), ("b", "c", 2.0), ("c", "d", 3.0), ("x", "a", 4.0)],
        "origem string, destino string, valor double")
    g = tc.Graph(df, directed=True)
    assert g.edges["a", "b"] == {"valor": 1.0}
    monkeypatch.setattr(around, "JOIN_ABOVE", 0)  # the broadcast-join path
    near = tc.neighborhood(df, start="a", hops=2)
    assert {n: near.nodes[n]["hop"] for n in near} == {"a": 0, "b": 1, "x": 1, "c": 2}
    nodes, edges = near.to_spark(spark, metrics=["degree"])
    assert nodes.count() == 4 and "degree" in nodes.columns


def test_statements_and_records(spark, monkeypatch):
    from tareco import tracing
    df = spark.createDataFrame(
        [("T1", "a1", "a2", -100.0), ("T2", "a2", "a1", 100.0), ("T3", "a2", "SHOP", -40.0)],
        "tid string, account string, counterparty string, amount double")
    g = tc.Graph(df, account="account", counterparty="counterparty", keep=True)
    assert set(g.edges) == {("a1", "a2"), ("a2", "SHOP")}
    found = tc.records(df, ["a1"], columns=["account"])
    assert [r["tid"] for r in found.collect()] == ["T1"]
    monkeypatch.setattr(tracing, "JOIN_ABOVE", 0)
    both = tc.records(df, ["SHOP", "a1"], columns=["account", "counterparty"])
    assert sorted(r["tid"] for r in both.collect()) == ["T1", "T2", "T3"]


def test_review_to_spark(spark):
    rows = [{"tid": f"T{k}", "from": "p", "to": f"q{k % 2}", "amount": 9500 + k, "date": f"2026-01-0{k + 1}"}
            for k in range(6)]
    g = tc.Graph(rows, directed=True, keep=True)
    first = g.review(limit=10_000).to_spark(spark).collect()[0]
    assert first["node"] == "p" and "T0" in first["ids"]


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

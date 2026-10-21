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

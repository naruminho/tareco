"""Runs examples/databricks_check.py cell by cell, the way Databricks would.

displayHTML and dbutils are stand-ins and DATABRICKS_RUNTIME_VERSION is set, so
tareco takes its Databricks paths. Needs pyspark and Java (skipped otherwise).
"""

import os
import shutil
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
NOTEBOOK = os.path.join(os.path.dirname(HERE), "examples", "databricks_check.py")


def cells():
    source = open(NOTEBOOK, encoding="utf-8").read()
    assert source.startswith("# Databricks notebook source")
    for chunk in source.split("# COMMAND ----------"):
        code = "\n".join(line for line in chunk.splitlines() if not line.startswith("# MAGIC")).strip()
        if code and not code.startswith("# Databricks notebook source"):
            yield code


def test_notebook_is_valid_python():
    for code in cells():
        compile(code, NOTEBOOK, "exec")


@pytest.fixture(scope="module")
def spark():
    pyspark = pytest.importorskip("pyspark")
    if not shutil.which("java") and not os.environ.get("JAVA_HOME"):
        pytest.skip("Spark needs Java")
    session = pyspark.sql.SparkSession.builder.master("local[2]").appName("tareco").getOrCreate()
    yield session


def test_notebook_runs_like_on_databricks(spark, monkeypatch, tmp_path):
    shown = []

    class Library:
        def restartPython(self):
            pass

    class DBUtils:
        library = Library()

    monkeypatch.setenv("DATABRICKS_RUNTIME_VERSION", "17.3")
    monkeypatch.setattr(sys.modules["__main__"], "displayHTML", shown.append, raising=False)
    monkeypatch.setattr("webbrowser.open", lambda url: pytest.fail("no browser on a cluster"))
    monkeypatch.chdir(tmp_path)
    tables = []
    namespace = {"spark": spark, "dbutils": DBUtils(), "displayHTML": shown.append,
                 "display": lambda df: tables.append(df.collect())}
    for code in cells():
        exec(compile(code, NOTEBOOK, "exec"), namespace)
    assert namespace["report"].ok, repr(namespace["report"])
    assert len(shown) == 5  # four graphs and the report
    assert len(tables) == 1 and tables[0][0]["node"] == "acc-1"  # the work list, as a Spark table
    for markup in shown:
        assert "<iframe srcdoc=" in markup and len(markup.encode()) <= 9e6
        assert all(ord(c) < 128 for c in markup)

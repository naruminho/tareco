# Databricks notebook source
# MAGIC %md
# MAGIC # tareco on Databricks
# MAGIC
# MAGIC Run all cells. `tareco.doctor(spark)` prints OK, FAIL or SKIP for each check;
# MAGIC every cell after it should draw an interactive graph right below it.

# COMMAND ----------

# MAGIC %pip install --quiet git+https://github.com/naruminho/tareco.git

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

import tareco

report = tareco.doctor(spark)
print(report)

# COMMAND ----------

# A small graph: the animated canvas view.
small = tareco.community_graph([20, 15, 10], seed=1)
small.show(title="Small graph")

# COMMAND ----------

# A big graph: the WebGL view, trimmed to fit the cell output limit.
big = tareco.scale_free_graph(60000, 3, seed=1)
big.show(title="60,000 nodes")

# COMMAND ----------

# Events from a Spark table, replayed with the time slider.
from pyspark.sql import functions as F

events = spark.range(20000).select(
    (F.col("id") % 1500).cast("string").alias("sender"),
    ((F.col("id") * 7 + 3) % 1500).cast("string").alias("receiver"),
    F.expr("date_add(DATE'2026-01-01', CAST(id % 180 AS INT))").alias("sent_at"),
)
timeline = tareco.timeline(events, time="sent_at")
timeline.show(title="Six months of events")

# COMMAND ----------

# The neighborhood of one node, queried in Spark without loading the table.
near = tareco.neighborhood(events, start="7", hops=2, source="sender", target="receiver")
near.show(color="hop", title="Around node 7")

# COMMAND ----------

# The shareable report, shown inline.
report_path = tareco.Graph(events.limit(3000)).report("/tmp/tareco_report.html", title="Report")
displayHTML(open(report_path, encoding="utf-8").read())

# COMMAND ----------

# Graph questions answered inside Spark: the results stay Spark tables.
edges = events.select(F.col("sender").alias("source"), F.col("receiver").alias("target"))
parts = tareco.big.components(edges)
print("separate parts:", parts.select("component").distinct().count())
print(tareco.big.degrees(edges).orderBy(F.desc("links")).limit(3).collect())
print(tareco.big.pagerank(edges, iterations=10).orderBy(F.desc("pagerank")).limit(3).collect())

# COMMAND ----------

# A work list as a Spark table, ready to save next to the data.
statements = spark.createDataFrame(
    [(f"T{k}", "acc-1", f"far-{k % 3}", -9500.0 - k, f"2026-03-0{k + 1}") for k in range(7)]
    + [(f"S{k}", f"acc-{k % 20 + 2}", f"shop-{k % 5}", -20.0 - k, "2026-03-01") for k in range(200)],
    "transaction_id string, account string, counterparty string, amount double, date string")
g = tareco.Graph(statements, account="account", counterparty="counterparty", keep=True)
display(g.review(limit=10_000).to_spark(spark))

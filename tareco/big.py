"""Graph questions answered inside Spark, for edge tables too big to bring to Python.

Everything here takes a Spark DataFrame of edges and returns a Spark DataFrame,
computed in the cluster with joins and aggregations (no GraphFrames, no RDDs, so
it runs on Spark Connect and Databricks serverless too). Bring back only what
you need, or save it next to the data:

    edges = tareco.big.statement_edges(spark.table("statements"), "account", "counterparty", "amount")
    tareco.big.components(edges).write.saveAsTable("account_components")
    near = tareco.neighborhood(edges, start="a017", hops=2)     # a small piece, as a Graph
"""

from .errors import TarecoError
from .io import SOURCE_COLUMNS, TARGET_COLUMNS, _is_dataframe, _is_spark, _pick_column


def _columns(edges, source, target):
    cols = list(edges.columns)
    s = _pick_column(cols, source, SOURCE_COLUMNS, "source")
    t = _pick_column(cols, target, TARGET_COLUMNS, "target", exclude=s)
    return s, t


def _spark(edges, what):
    if not _is_spark(edges):
        raise TarecoError(f"tareco.big.{what} works on Spark DataFrames; for a table that fits in memory, "
                          f"load it with tareco.Graph(...) and ask the graph")
    from pyspark.sql import functions as F
    return F


def _settle(df):
    """Cut the query plan between iterations, or it grows with every round."""
    for method in ("localCheckpoint", "checkpoint"):
        try:
            return getattr(df, method)()
        except Exception:
            continue
    return df.cache()


# ------------------------------------------------------------------- statements

def statement_edges(statements, account, counterparty, amount):
    """Bank statements (one row per entry, money out negative) as edges ``source, target, amount``.

    Money out goes from the account to the counterparty; money in, from the
    counterparty to the account. A transfer between two accounts that both have
    statements in the table shows up twice and is kept once, from the side it left.
    Works on Spark (lazily, in the cluster) and pandas DataFrames.
    """
    for col in (account, counterparty, amount):
        if col not in list(statements.columns):
            raise TarecoError(f"no column {col!r}; columns are {list(statements.columns)}")
    others = [c for c in statements.columns if c not in (account, counterparty, amount, "source", "target")]
    if _is_spark(statements):
        from pyspark.sql import functions as F
        owners = statements.select(F.col(account).alias("__owner")).distinct()
        out = statements.filter(F.col(amount) < 0).select(
            F.col(account).alias("source"), F.col(counterparty).alias("target"),
            (-F.col(amount)).alias(amount), *others)
        incoming = statements.filter(F.col(amount) > 0)
        incoming = incoming.join(owners, incoming[counterparty] == owners["__owner"], "left_anti")
        inn = incoming.select(F.col(counterparty).alias("source"), F.col(account).alias("target"),
                              F.col(amount), *others)
        return out.unionByName(inn)
    if _is_dataframe(statements):
        import pandas as pd
        owners = set(statements[account].dropna())
        out = statements[statements[amount] < 0]
        inn = statements[(statements[amount] > 0) & ~statements[counterparty].isin(owners)]
        a = pd.DataFrame({"source": out[account], "target": out[counterparty], amount: -out[amount]})
        b = pd.DataFrame({"source": inn[counterparty], "target": inn[account], amount: inn[amount]})
        for c in others:
            a[c], b[c] = out[c], inn[c]
        return pd.concat([a, b], ignore_index=True)
    raise TarecoError("statement_edges works on Spark and pandas DataFrames")


# --------------------------------------------------------------------- degrees

def degrees(edges, source=None, target=None, weight=None):
    """``node, out_links, in_links, links`` (and ``out_weight, in_weight`` with ``weight``) per node."""
    F = _spark(edges, "degrees")
    s, t = _columns(edges, source, target)
    w = F.col(weight) if weight else F.lit(1.0)
    out = edges.groupBy(F.col(s).alias("node")).agg(F.countDistinct(t).alias("out_links"),
                                                      F.sum(w).alias("out_weight"))
    inn = edges.groupBy(F.col(t).alias("node")).agg(F.countDistinct(s).alias("in_links"),
                                                     F.sum(w).alias("in_weight"))
    both = out.join(inn, "node", "full_outer").fillna(0, subset=["out_links", "in_links", "out_weight", "in_weight"])
    both = both.withColumn("links", F.col("out_links") + F.col("in_links"))
    cols = ["node", "out_links", "in_links", "links"] + (["out_weight", "in_weight"] if weight else [])
    return both.select(*cols)


# ------------------------------------------------------------------ components

def _pairs(edges, s, t, F):
    """Both directions of every link, as ``src, dst`` text."""
    a = edges.select(F.col(s).cast("string").alias("src"), F.col(t).cast("string").alias("dst"))
    return a.unionByName(a.select(F.col("dst").alias("src"), F.col("src").alias("dst"))) \
        .filter(F.col("src").isNotNull() & F.col("dst").isNotNull() & (F.col("src") != F.col("dst"))).distinct()


def components(edges, source=None, target=None, max_iter=60):
    """``node, component`` for every node: the separate parts of the network, direction ignored.

    Components are numbered by size, 1 for the biggest. Each round every node takes
    the smallest label around it, until nothing changes.
    """
    F = _spark(edges, "components")
    from pyspark.sql import Window
    s, t = _columns(edges, source, target)
    pairs = _settle(_pairs(edges, s, t, F))
    labels = _settle(pairs.select(F.col("src").alias("node")).distinct().withColumn("label", F.col("node")))
    for _ in range(max_iter):
        seen = pairs.join(labels, pairs["src"] == labels["node"]).groupBy(F.col("dst").alias("node")) \
            .agg(F.min("label").alias("seen"))
        new = labels.join(seen, "node", "left").select(
            "node", F.least(F.col("label"), F.coalesce(F.col("seen"), F.col("label"))).alias("label"))
        new = _settle(new)
        changed = new.join(labels.withColumnRenamed("label", "old"), "node").filter(F.col("label") != F.col("old"))
        labels = new
        if changed.limit(1).count() == 0:
            break
    sizes = labels.groupBy("label").agg(F.count("*").alias("size"))
    numbered = sizes.withColumn("component", F.row_number().over(Window.orderBy(F.desc("size"), F.col("label"))))
    return labels.join(numbered, "label").select("node", "component")


# -------------------------------------------------------------------- pagerank

def pagerank(edges, source=None, target=None, weight=None, alpha=0.85, iterations=20):
    """``node, pagerank`` for every node, following the links' direction (and ``weight``)."""
    F = _spark(edges, "pagerank")
    s, t = _columns(edges, source, target)
    w = F.col(weight).cast("double") if weight else F.lit(1.0)
    links = edges.select(F.col(s).cast("string").alias("src"), F.col(t).cast("string").alias("dst"), w.alias("w")) \
        .filter(F.col("src").isNotNull() & F.col("dst").isNotNull()).groupBy("src", "dst").agg(F.sum("w").alias("w"))
    out = links.groupBy("src").agg(F.sum("w").alias("out_w"))
    links = _settle(links.join(out, "src").withColumn("share", F.col("w") / F.col("out_w")).select("src", "dst", "share"))
    nodes = _settle(links.select(F.col("src").alias("node")).union(links.select(F.col("dst").alias("node"))).distinct())
    n = nodes.count()
    if n == 0:
        return nodes.withColumn("pagerank", F.lit(0.0))
    senders = _settle(out.select(F.col("src").alias("node")).withColumn("sends", F.lit(True)))
    ranks = nodes.withColumn("rank", F.lit(1.0 / n))
    for _ in range(iterations):
        dangling = ranks.join(senders, "node", "left").filter(F.col("sends").isNull()) \
            .agg(F.sum("rank").alias("d")).collect()[0]["d"] or 0.0
        got = links.join(ranks, links["src"] == ranks["node"]).groupBy(F.col("dst").alias("node")) \
            .agg(F.sum(F.col("rank") * F.col("share")).alias("got"))
        base = (1 - alpha) / n + alpha * dangling / n
        ranks = _settle(nodes.join(got, "node", "left")
                        .select("node", (F.lit(base) + alpha * F.coalesce(F.col("got"), F.lit(0.0))).alias("rank")))
    return ranks.withColumnRenamed("rank", "pagerank")


# ----------------------------------------------------------------- communities

def communities(edges, source=None, target=None, weight=None, iterations=10):
    """``node, community`` for every node, by label propagation: each node joins the label
    its neighbors weigh most. Fast and good on big graphs; on graphs that fit in memory,
    ``Graph.communities()`` (Louvain) is sharper. Communities are numbered by size."""
    F = _spark(edges, "communities")
    from pyspark.sql import Window
    s, t = _columns(edges, source, target)
    w = F.col(weight).cast("double") if weight else F.lit(1.0)
    a = edges.select(F.col(s).cast("string").alias("src"), F.col(t).cast("string").alias("dst"), w.alias("w"))
    pairs = a.unionByName(a.select(F.col("dst").alias("src"), F.col("src").alias("dst"), "w")) \
        .filter(F.col("src").isNotNull() & F.col("dst").isNotNull() & (F.col("src") != F.col("dst"))) \
        .groupBy("src", "dst").agg(F.sum("w").alias("w"))
    pairs = _settle(pairs)
    labels = _settle(pairs.select(F.col("src").alias("node")).distinct().withColumn("label", F.col("node")))
    # each node also votes for the label it has, as much as an average neighbor: without it
    # two linked nodes swap labels forever
    own = _settle(pairs.groupBy(F.col("src").alias("node")).agg(F.avg("w").alias("self_w")))
    pick = Window.partitionBy("node").orderBy(F.desc("weight"), F.col("label"))
    for _ in range(iterations):
        theirs = pairs.join(labels, pairs["src"] == labels["node"]).select(F.col("dst").alias("node"), "label", "w")
        mine = labels.join(own, "node").select("node", "label", F.col("self_w").alias("w"))
        votes = theirs.unionByName(mine).groupBy("node", "label").agg(F.sum("w").alias("weight"))
        best = votes.withColumn("r", F.row_number().over(pick)).filter(F.col("r") == 1).select("node", "label")
        new = _settle(labels.select("node").join(best, "node", "left")
                      .join(labels.withColumnRenamed("label", "old"), "node")
                      .select("node", F.coalesce(F.col("label"), F.col("old")).alias("label")))
        changed = new.join(labels.withColumnRenamed("label", "old"), "node").filter(F.col("label") != F.col("old"))
        labels = new
        if changed.limit(1).count() == 0:
            break
    sizes = labels.groupBy("label").agg(F.count("*").alias("size"))
    numbered = sizes.withColumn("community", F.row_number().over(Window.orderBy(F.desc("size"), F.col("label"))))
    return labels.join(numbered, "label").select("node", "community")

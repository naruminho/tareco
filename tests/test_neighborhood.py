import pytest

import tareco as tc
from tareco import metrics

EDGES = [
    {"from": "a", "to": "b", "w": 1}, {"from": "b", "to": "c", "w": 2}, {"from": "c", "to": "d", "w": 3},
    {"from": "d", "to": "e", "w": 4}, {"from": "x", "to": "a", "w": 5}, {"from": "y", "to": "z", "w": 6},
    {"from": "b", "to": "x", "w": 7},
]


def test_hops_from_rows():
    g = tc.neighborhood(EDGES, start="a", hops=2)
    assert {n: g.nodes[n]["hop"] for n in g} == {"a": 0, "b": 1, "x": 1, "c": 2}
    assert g.has_edge("b", "x") and g.edges["b", "c"] == {"w": 2}
    assert not g.has_edge("c", "d")  # d is three steps away
    assert g.attrs["start"] == ["a"] and not g.attrs["truncated"]


def test_direction_and_several_starts():
    out = tc.neighborhood(EDGES, start="a", hops=3, direction="out", directed=True)
    assert set(out) == {"a", "b", "c", "x", "d"}
    back = tc.neighborhood(EDGES, start="c", hops=2, direction="in", directed=True)
    assert set(back) == {"c", "b", "a"}
    both = tc.neighborhood(EDGES, start=["a", "y"], hops=1)
    assert set(both) == {"a", "b", "x", "y", "z"}
    with pytest.raises(tc.TarecoError):
        tc.neighborhood(EDGES, start="a", direction="sideways")
    with pytest.raises(tc.TarecoError):
        tc.neighborhood(EDGES, start=[])


def test_max_nodes_keeps_the_busiest():
    rows = [("hub", f"leaf{i}") for i in range(20)] + [("hub", "busy"), ("busy", "x"), ("busy", "y")]
    rows += [("a", "busy"), ("b", "busy")]
    g = tc.neighborhood(rows, start="hub", hops=1, max_nodes=5)
    assert len(g) == 5 and g.attrs["truncated"]
    assert "busy" not in g or g.nodes["busy"]["hop"] == 1


def test_pandas_and_csv(tmp_path):
    pd = pytest.importorskip("pandas")
    df = pd.DataFrame(EDGES)
    g = tc.neighborhood(df, start="d", hops=1)
    assert set(g) == {"d", "c", "e"}
    path = tmp_path / "edges.csv"
    df.to_csv(path, index=False)
    assert set(tc.neighborhood(str(path), start="d", hops=1)) == {"d", "c", "e"}


def test_show_by_hop():
    g = tc.neighborhood(EDGES, start="a", hops=2)
    from tareco.viz import build_payload
    legend = build_payload(g, color="hop")["config"]["legend"]
    assert legend["kind"] == "category" and [it["label"] for it in legend["items"]] == ["0", "1", "2"]


# -------------------------------------------------------------------- exports

def test_to_pandas_with_metrics():
    pytest.importorskip("pandas")
    g = tc.Graph([("a", "b"), ("b", "c")], nodes={"a": {"team": "x"}})
    nodes, edges = g.to_pandas(metrics=["degree", "pagerank", "community"])
    assert list(nodes.columns[:2]) == ["id", "team"]
    assert dict(zip(nodes["id"], nodes["degree"])) == {"a": 1, "b": 2, "c": 1}
    assert nodes["pagerank"].sum() == pytest.approx(1.0)
    assert set(nodes["community"]) <= {1, 2, 3}
    with pytest.raises(tc.TarecoError, match="unknown metric"):
        g.to_pandas(metrics=["fame"])
    empty_nodes, empty_edges = tc.Graph().to_pandas()
    assert list(empty_nodes.columns) == ["id"] and list(empty_edges.columns) == ["source", "target"]


class FakeSpark:
    def __init__(self):
        self.calls = []

    def createDataFrame(self, data, schema):
        self.calls.append((data, schema))
        return (data, schema)


def test_to_spark_builds_typed_tables():
    g = tc.Graph([(1, "a", 2.5), ("a", "b")], nodes={1: {"score": 3, "tags": ["p", "q"]}, "b": {"score": 1.5}})
    spark = FakeSpark()
    (node_data, node_cols), (edge_data, edge_cols) = g.to_spark(spark, metrics=["degree"])
    assert node_cols == ["id", "score", "tags", "degree"]
    assert node_data[0] == ("1", 3.0, "['p', 'q']", 1)  # mixed ids become text; ints and floats unify
    assert edge_cols == ["source", "target", "weight"]
    assert set(edge_data) == {("1", "a", 2.5), ("b", "a", None)}
    data, schema = metrics._spark_frame(FakeSpark(), [], ["source", "target"])
    assert data == [] and schema == "`source` string, `target` string"


def test_explanation_table():
    pytest.importorskip("pandas")
    df = tc.Graph([("a", "b"), ("b", "c")]).explain().to_pandas()
    assert list(df.columns) == ["kind", "text", "group", "nodes"] and df["kind"][0] == "overview"

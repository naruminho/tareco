import json

import pytest

import tareco as tc
from tareco import TarecoError


def write(path, text):
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_list_of_pairs_and_weights():
    g = tc.Graph([("a", "b"), ("b", "c", 2.5)])
    assert g.edges["b", "c"] == {"weight": 2.5}


def test_plain_list_is_nodes():
    g = tc.Graph(["a", "b"])
    assert list(g.nodes) == ["a", "b"] and g.edge_count == 0


def test_adjacency_dicts():
    g = tc.Graph({"a": ["b", "c"], "b": {"c": 3, "d": {"kind": "x"}}, "e": [], "f": "a"})
    assert g.edges["b", "c"] == {"weight": 3}
    assert g.edges["b", "d"] == {"kind": "x"}
    assert "e" in g and g.degree("e") == 0
    assert g.has_edge("f", "a")


def test_records_guess_columns_in_portuguese():
    rows = [{"origem": "ana", "destino": "bia", "valor": 10},
            {"origem": "bia", "destino": "caio", "valor": 5}]
    g = tc.Graph(rows)
    assert g.edges["ana", "bia"] == {"valor": 10}


def test_records_fall_back_to_first_columns():
    rows = [{"x": 1, "y": 2, "kind": "k"}]
    g = tc.Graph(rows)
    assert g.has_edge(1, 2) and g.edges[1, 2] == {"kind": "k"}


def test_records_explicit_columns_and_errors():
    rows = [{"a": 1, "b": 2, "c": 3}]
    g = tc.Graph(rows, source="c", target="a")
    assert g.has_edge(3, 1) and g.edges[3, 1] == {"b": 2}
    with pytest.raises(TarecoError, match="no column 'zz'"):
        tc.Graph(rows, source="zz")


def test_record_with_empty_target_adds_lonely_node():
    g = tc.Graph([{"source": "a", "target": None}, {"source": "b", "target": "c"}])
    assert "a" in g and g.degree("a") == 0 and g.edge_count == 1


def test_node_link_dict_and_directed_flag():
    data = {"directed": True,
            "nodes": [{"id": "a", "group": 1}, {"id": "b"}],
            "links": [{"source": "a", "target": "b", "weight": 2}]}
    g = tc.Graph(data)
    assert g.directed and g.nodes["a"] == {"group": 1} and g.edges["a", "b"] == {"weight": 2}


def test_nodes_argument_kinds():
    edges = [("a", "b")]
    g = tc.Graph(edges, nodes=[{"name": "a", "age": 30}, {"name": "z", "age": 1}])
    assert g.nodes["a"] == {"age": 30} and "z" in g
    g = tc.Graph(edges, nodes={"a": {"age": 3}, "b": 7})
    assert g.nodes["a"] == {"age": 3} and g.nodes["b"] == {"value": 7}
    assert list(tc.Graph(edges, nodes=["c", "a"]).nodes) == ["c", "a", "b"]


def test_csv_files(tmp_path):
    edges = write(tmp_path / "e.csv", "from;to;peso\nana;bia;2\nbia;caio;1,5\ncaio;;\n")
    nodes = write(tmp_path / "n.csv", "nome,idade,ativo\nana,30,true\nbia,25,false\n")
    g = tc.read_csv(edges, nodes)
    assert g.edges["ana", "bia"] == {"peso": 2}
    assert g.edges["bia", "caio"] == {"peso": 1.5}
    assert g.nodes["ana"] == {"idade": 30, "ativo": True}
    assert g.nodes["bia"]["ativo"] is False
    assert "caio" in g and g.edge_count == 2


def test_csv_numbers_and_bom(tmp_path):
    path = tmp_path / "e.csv"
    path.write_bytes("﻿source,target,w\n1,2,0.5\n2,3,\n".encode("utf-8"))
    g = tc.Graph(str(path))
    assert g.has_edge(1, 2) and g.edges[1, 2] == {"w": 0.5}
    assert g.edges[2, 3] == {}


def test_edgelist_file(tmp_path):
    path = write(tmp_path / "g.edges", "# comment\na b 3\nb c\n\n")
    g = tc.Graph(path)
    assert g.edges["a", "b"] == {"weight": 3} and g.has_edge("b", "c")


def test_missing_file():
    with pytest.raises(TarecoError, match="file not found"):
        tc.Graph("nope/nothing.csv")


def test_cannot_read_scalars():
    with pytest.raises(TarecoError):
        tc.Graph(42)


def test_json_roundtrip(tmp_path):
    g = tc.Graph(directed=True, title="t")
    g.add_node("a", tags=["x", "y"])
    g.add_edge("a", "b", weight=1.5)
    path = tmp_path / "g.json"
    g.to_json(str(path))
    h = tc.read_json(str(path))
    assert h.directed and h.attrs == {"title": "t"}
    assert h.nodes["a"] == {"tags": ["x", "y"]} and h.edges["a", "b"] == {"weight": 1.5}
    assert json.loads(g.to_json())["attrs"] == {"title": "t"}


def test_csv_roundtrip(tmp_path):
    g = tc.Graph([("a", "b", 2), ("b", "c")], nodes={"a": {"age": 3}})
    e, n = tmp_path / "e.csv", tmp_path / "n.csv"
    g.to_csv(str(e), str(n))
    h = tc.read_csv(str(e), str(n))
    assert set(h.edges) == set(g.edges)
    assert h.edges["a", "b"] == {"weight": 2} and h.edges["b", "c"] == {}
    assert h.nodes["a"] == {"age": 3}


def test_graph_from_graph_keeps_direction():
    d = tc.Graph([("a", "b")], directed=True)
    assert tc.Graph(d).directed
    both = tc.Graph(tc.Graph([("a", "b")]), directed=True)
    assert both.has_edge("a", "b") and both.has_edge("b", "a")


def test_pandas_interop():
    pd = pytest.importorskip("pandas")
    edges = pd.DataFrame({"from": ["a", "b"], "to": ["b", "c"], "w": [1.0, float("nan")]})
    nodes = pd.DataFrame({"id": ["a", "b"], "group": ["x", None]})
    g = tc.Graph(edges, nodes=nodes)
    assert g.edges["a", "b"] == {"w": 1.0} and g.edges["b", "c"] == {}
    assert g.nodes["a"] == {"group": "x"} and g.nodes["b"] == {}
    n, e = g.to_pandas()
    assert list(e.columns[:2]) == ["source", "target"] and len(e) == 2 and len(n) == 3


def test_networkx_interop():
    nx = pytest.importorskip("networkx")
    G = nx.DiGraph()
    G.add_edge("a", "b", weight=2)
    G.nodes["a"]["color"] = "red"
    g = tc.Graph(G)
    assert g.directed and g.edges["a", "b"] == {"weight": 2} and g.nodes["a"] == {"color": "red"}
    back = g.to_networkx()
    assert back.is_directed() and back["a"]["b"]["weight"] == 2

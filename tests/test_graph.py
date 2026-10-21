import pytest

import tareco as tc
from tareco import EdgeNotFound, NodeNotFound, TarecoError


def test_add_and_query():
    g = tc.Graph()
    g.add_node("a", color="red")
    g.add_edge("a", "b", weight=2)
    g.add_edge("b", "c")
    assert len(g) == 3
    assert g.edge_count == 2
    assert list(g.nodes) == ["a", "b", "c"]
    assert set(g.edges) == {("a", "b"), ("b", "c")}
    assert g.nodes["a"] == {"color": "red"}
    assert g.edges["b", "a"] == {"weight": 2}
    assert g.has_edge("b", "a") and not g.has_edge("a", "c")
    assert "a" in g and "z" not in g and ["unhashable"] not in g
    assert sorted(g.neighbors("b")) == ["a", "c"]


def test_attributes_update_instead_of_duplicate():
    g = tc.Graph()
    g.add_edge("a", "b", weight=1)
    g.add_edge("b", "a", label="x")
    assert g.edge_count == 1
    assert g.edges["a", "b"] == {"weight": 1, "label": "x"}
    g.add_node("a", size=3)
    g.add_node("a", color="blue")
    assert g.nodes["a"] == {"size": 3, "color": "blue"}


def test_add_edges_formats():
    g = tc.Graph()
    g.add_edges([("a", "b"), ("b", "c", 4), ("c", "d", {"kind": "x"})])
    assert g.edges["b", "c"] == {"weight": 4}
    assert g.edges["c", "d"] == {"kind": "x"}
    with pytest.raises(TarecoError):
        g.add_edges([("a", "b", 1, 2)])


def test_add_nodes_with_attributes_and_tuple_ids():
    g = tc.Graph()
    g.add_nodes(["a", ("b", {"x": 1}), (1, 2)])
    assert list(g.nodes) == ["a", "b", (1, 2)]
    assert g.nodes["b"] == {"x": 1}


def test_none_is_not_a_node():
    with pytest.raises(TarecoError):
        tc.Graph().add_node(None)


def test_directed():
    g = tc.Graph(directed=True)
    g.add_edges([("a", "b"), ("b", "c"), ("c", "a"), ("a", "c")])
    assert g.successors("a") == ["b", "c"]
    assert sorted(g.predecessors("a")) == ["c"]
    assert g.out_degree("a") == 2 and g.in_degree("a") == 1 and g.degree("a") == 3
    assert not g.has_edge("b", "a")
    assert set(g.edges) == {("a", "b"), ("b", "c"), ("c", "a"), ("a", "c")}


def test_degree_weighted_and_self_loops():
    g = tc.Graph()
    g.add_edge("a", "b", weight=3)
    g.add_edge("a", "a", weight=1)
    assert g.degree("a") == 3  # self-loop counts twice
    assert g.degree("a", weight="weight") == 5
    assert g.degree() == {"a": 3, "b": 1}
    assert g.edge_count == 2
    assert set(g.edges) == {("a", "b"), ("a", "a")}


def test_remove():
    g = tc.Graph([("a", "b"), ("b", "c"), ("c", "c")])
    g.remove_edge("c", "b")
    assert g.edge_count == 2 and not g.has_edge("b", "c")
    g.remove_node("c")
    assert list(g.nodes) == ["a", "b"] and g.edge_count == 1
    with pytest.raises(EdgeNotFound):
        g.remove_edge("a", "z")
    with pytest.raises(NodeNotFound):
        g.remove_node("z")

    d = tc.Graph([("a", "b"), ("b", "a"), ("c", "b")], directed=True)
    d.remove_node("b")
    assert d.edge_count == 0 and list(d.nodes) == ["a", "c"]


def test_missing_node_errors_are_key_errors():
    g = tc.Graph([("a", "b")])
    with pytest.raises(KeyError):
        g.nodes["z"]
    with pytest.raises(KeyError):
        g.edges["a", "z"]
    with pytest.raises(NodeNotFound, match="'z'"):
        g.neighbors("z")


def test_copy_is_independent():
    g = tc.Graph([("a", "b", 1)], title="t")
    h = g.copy()
    h.edges["a", "b"]["weight"] = 9
    h.add_edge("b", "c")
    assert g.edges["a", "b"]["weight"] == 1 and g.edge_count == 1
    assert h.attrs == {"title": "t"}


def test_subgraph_and_ego():
    g = tc.path_graph(6)
    s = g.subgraph([1, 2, 3, 99])
    assert list(s.nodes) == [1, 2, 3] and set(s.edges) == {(1, 2), (2, 3)}
    e = g.ego(3, radius=2)
    assert list(e.nodes) == [1, 2, 3, 4, 5]


def test_reverse_and_conversions():
    d = tc.Graph([("a", "b", 2)], directed=True)
    r = d.reverse()
    assert r.has_edge("b", "a") and not r.has_edge("a", "b")
    assert r.edges["b", "a"] == {"weight": 2}
    u = d.to_undirected()
    assert not u.directed and u.has_edge("b", "a")
    dd = tc.Graph([("a", "b")]).to_directed()
    assert dd.directed and dd.has_edge("a", "b") and dd.has_edge("b", "a")


def test_repr():
    assert repr(tc.Graph([("a", "b")])) == "<Graph undirected, 2 nodes, 1 edges>"
    assert "directed, 0 nodes" in repr(tc.Graph(directed=True))
    assert repr(tc.Graph([("a", "b")]).nodes) == "NodeView(['a', 'b'])"

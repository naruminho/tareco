import math

import pytest

import tareco as tc
from tareco import HasCycle, NoPath, NotConnected, TarecoError


def two_triangles():
    return tc.Graph([("a", "b"), ("b", "c"), ("c", "a"), ("c", "d"),
                     ("d", "e"), ("e", "f"), ("f", "d")])


# ------------------------------------------------------------------ paths

def test_shortest_path_unweighted_and_weighted():
    g = tc.Graph([("a", "b", 10), ("a", "c", 1), ("c", "d", 1), ("d", "b", 1)])
    assert g.shortest_path("a", "b") == ["a", "b"]
    assert g.shortest_path("a", "b", weight="weight") == ["a", "c", "d", "b"]
    assert g.distance("a", "b") == 1
    assert g.distance("a", "b", weight="weight") == 3
    assert g.distances("a") == {"a": 0, "b": 1, "c": 1, "d": 2}
    assert g.distances("a", weight="weight") == {"a": 0, "c": 1, "d": 2, "b": 3}


def test_shortest_path_respects_direction():
    g = tc.Graph([("a", "b"), ("b", "c")], directed=True)
    assert g.shortest_path("a", "c") == ["a", "b", "c"]
    with pytest.raises(NoPath):
        g.shortest_path("c", "a")
    with pytest.raises(NoPath):
        g.distance("c", "a", weight="weight")


def test_shortest_path_errors():
    g = tc.Graph([("a", "b", -1)])
    with pytest.raises(TarecoError, match="negative"):
        g.shortest_path("a", "b", weight="weight")
    with pytest.raises(tc.NodeNotFound):
        g.shortest_path("a", "zz")
    assert g.shortest_path("a", "a") == ["a"]


def test_bfs_dfs():
    g = tc.Graph([(1, 2), (1, 3), (2, 4), (3, 5)])
    assert g.bfs(1) == [1, 2, 3, 4, 5]
    assert g.dfs(1) == [1, 2, 4, 3, 5]


def test_diameter():
    assert tc.path_graph(5).diameter() == 4
    assert tc.cycle_graph(6).diameter() == 3
    with pytest.raises(NotConnected):
        tc.Graph([("a", "b"), ("c", "d")]).diameter()


# ------------------------------------------------------------- centrality

def test_pagerank_basics():
    pr = tc.cycle_graph(5).pagerank()
    assert all(math.isclose(v, 0.2) for v in pr.values())
    star = tc.star_graph(4).pagerank()
    assert math.isclose(sum(star.values()), 1.0)
    assert max(star, key=star.get) == 0


def test_pagerank_directed_with_dangling_node():
    pr = tc.Graph([("a", "b"), ("b", "c")], directed=True).pagerank()
    assert math.isclose(sum(pr.values()), 1.0)
    assert pr["c"] > pr["b"] > pr["a"]


def test_pagerank_weights_matter():
    g = tc.Graph([("a", "b", 9), ("a", "c", 1)], directed=True)
    pr = g.pagerank()
    assert pr["b"] > pr["c"]
    assert math.isclose(g.pagerank(weight=None)["b"], g.pagerank(weight=None)["c"])


def test_betweenness():
    star = tc.star_graph(4).betweenness()
    assert star[0] == 1.0 and star[1] == 0.0
    path = tc.path_graph(5).betweenness()
    assert path[2] == pytest.approx(4 / 6) and path[1] == pytest.approx(3 / 6)
    raw = tc.path_graph(3).betweenness(normalized=False)
    assert raw == {0: 0.0, 1: 1.0, 2: 0.0}


def test_betweenness_weighted_follows_cheap_route():
    g = tc.Graph([("a", "b", 10), ("a", "c", 1), ("c", "b", 1)])
    assert g.betweenness(weight="weight")["c"] > 0
    assert g.betweenness()["c"] == 0


def test_closeness_and_degree_centrality():
    star = tc.star_graph(4)
    assert star.closeness()[0] == 1.0
    assert star.closeness()[1] == pytest.approx(4 / 7)
    assert star.degree_centrality()[0] == 1.0
    lonely = tc.Graph([("a", "b")], nodes=["c"])
    assert lonely.closeness()["c"] == 0.0
    assert lonely.closeness()["a"] == pytest.approx(1 / 2)


# ------------------------------------------------------------ communities

def test_communities_two_triangles():
    g = two_triangles()
    comms = g.communities()
    assert sorted(map(sorted, comms)) == [["a", "b", "c"], ["d", "e", "f"]]
    assert g.modularity(comms) == pytest.approx(5 / 14)


def test_communities_recover_planted_groups():
    g = tc.community_graph([30, 30, 30], p_in=0.4, p_out=0.01, seed=7)
    comms = g.communities()
    assert len(comms) == 3
    for c in comms:
        assert len({g.nodes[n]["group"] for n in c}) == 1


def test_communities_edge_cases():
    assert tc.Graph().communities() == []
    assert tc.Graph(["a", "b"]).communities() == [{"a"}, {"b"}]
    assert two_triangles().communities(seed=None)  # random order still works


def test_modularity_validation():
    g = two_triangles()
    with pytest.raises(TarecoError):
        g.modularity([{"a", "b"}])
    with pytest.raises(TarecoError):
        g.modularity([{"a", "b", "c"}, {"c", "d", "e", "f"}])
    assert g.modularity([set(g)]) == pytest.approx(0.0)


# ---------------------------------------------------------------- structure

def test_components():
    g = tc.Graph([("a", "b"), ("c", "d"), ("d", "e")], nodes=["z"])
    assert g.components() == [{"c", "d", "e"}, {"a", "b"}, {"z"}]
    assert not g.is_connected() and tc.path_graph(3).is_connected()
    assert not tc.Graph().is_connected()


def test_strong_components():
    g = tc.Graph([("a", "b"), ("b", "c"), ("c", "a"), ("c", "d"), ("d", "e"), ("e", "d")],
                 directed=True)
    assert g.strong_components() == [{"a", "b", "c"}, {"d", "e"}]
    singles = tc.path_graph(4, directed=True).strong_components()
    assert sorted(map(len, singles)) == [1, 1, 1, 1]


def test_strong_components_deep_graph_does_not_recurse():
    g = tc.cycle_graph(20000, directed=True)
    assert len(g.strong_components()) == 1


def test_clustering_and_triangles():
    g = two_triangles()
    assert g.triangles("a") == 1 and g.triangles()["c"] == 1
    assert g.clustering("a") == 1.0
    assert g.clustering("c") == pytest.approx(1 / 3)
    assert tc.star_graph(3).clustering(0) == 0.0
    assert tc.complete_graph(4).transitivity() == 1.0


def test_core_number_and_k_core():
    g = tc.complete_graph(4)
    g.add_edge(3, "tail")
    core = g.core_number()
    assert core["tail"] == 1 and core[0] == 3
    assert set(g.k_core().nodes) == {0, 1, 2, 3}
    assert set(g.k_core(1).nodes) == set(g.nodes)


def test_spanning_tree():
    g = tc.Graph([("a", "b", 1), ("b", "c", 2), ("a", "c", 5), ("c", "d", 1)])
    t = g.spanning_tree()
    assert set(map(frozenset, t.edges)) == {frozenset("ab"), frozenset("bc"), frozenset("cd")}
    m = g.spanning_tree(maximum=True)
    assert frozenset("ac") in set(map(frozenset, m.edges))
    forest = tc.Graph([("a", "b"), ("c", "d")]).spanning_tree()
    assert forest.edge_count == 2


def test_topological_sort_and_cycles():
    dag = tc.Graph([("shop", "cook"), ("cook", "eat"), ("shop", "eat")], directed=True)
    assert dag.topological_sort() == ["shop", "cook", "eat"]
    assert not dag.has_cycle()
    dag.add_edge("eat", "shop")
    assert dag.has_cycle()
    with pytest.raises(HasCycle):
        dag.topological_sort()
    with pytest.raises(TarecoError):
        tc.path_graph(3).topological_sort()
    assert not tc.path_graph(4).has_cycle() and tc.cycle_graph(4).has_cycle()
    assert tc.Graph([("a", "a")]).has_cycle()


def test_density():
    assert tc.complete_graph(5).density() == 1.0
    assert tc.complete_graph(4, directed=True).density() == 1.0
    assert tc.Graph(["a"]).density() == 0.0


def test_suggest_links():
    g = tc.Graph([("ana", "bia"), ("ana", "caio"), ("bia", "davi"), ("caio", "davi"), ("davi", "eva")])
    best = g.suggest_links(top=1)
    assert [tuple(sorted(best[0][:2]))] == [("ana", "davi")]
    for u, v, s in g.suggest_links():
        assert not g.has_edge(u, v) and s > 0
    assert all("eva" in (u, v) for u, v, _ in g.suggest_links("eva"))


def test_summary():
    s = two_triangles().summary()
    assert s["nodes"] == 6 and s["edges"] == 7 and s["components"] == 1
    assert s["top_nodes"][0][0] in ("c", "d")
    text = repr(s)
    assert "average clustering" in text and "top nodes" in text
    assert tc.Graph().summary()["nodes"] == 0


# --------------------------------------------------------------- generators

def test_generators():
    assert tc.complete_graph(5).edge_count == 10
    assert tc.complete_graph(3, directed=True).edge_count == 6
    assert tc.path_graph(4).edge_count == 3
    assert tc.cycle_graph(4).edge_count == 4
    assert tc.star_graph(5).degree(0) == 5
    grid = tc.grid_graph(3, 4)
    assert len(grid) == 12 and grid.edge_count == 17 and grid.has_edge((0, 0), (0, 1))
    r1, r2 = tc.random_graph(50, 0.1, seed=1), tc.random_graph(50, 0.1, seed=1)
    assert set(r1.edges) == set(r2.edges) and r1.edge_count > 0
    sf = tc.scale_free_graph(200, 2, seed=1)
    assert len(sf) == 200 and sf.is_connected()
    assert max(sf.degree().values()) > 15  # hubs
    sw = tc.small_world_graph(30, 4, 0.2, seed=1)
    assert len(sw) == 30 and sw.edge_count == 60
    with pytest.raises(TarecoError):
        tc.scale_free_graph(3, 5)
    with pytest.raises(TarecoError):
        tc.small_world_graph(4, 6)

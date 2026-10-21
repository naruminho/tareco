import random

import pytest

import tareco as tc


def test_max_flow_small_network():
    g = tc.Graph(directed=True)
    g.add_edges([("s", "a", 3), ("s", "b", 2), ("a", "b", 1), ("a", "t", 2), ("b", "t", 3)])
    flow = g.max_flow("s", "t")
    assert flow.value == 5
    assert flow.flows[("s", "a")] + flow.flows[("s", "b")] == 5
    assert sum(c for _, _, c in flow.cut) == 5
    assert "s" in flow.side and "t" not in flow.side
    assert repr(flow).startswith("<Flow value=5")


def test_max_flow_undirected_and_defaults():
    g = tc.Graph([("a", "b"), ("b", "c"), ("a", "c")])
    assert g.max_flow("a", "c").value == 2  # unit capacities, two routes
    assert g.max_flow("c", "a").value == 2
    with pytest.raises(tc.TarecoError):
        g.max_flow("a", "a")
    with pytest.raises(tc.TarecoError, match="negative"):
        tc.Graph([("a", "b", -1)]).max_flow("a", "b")
    lonely = tc.Graph([("a", "b")], nodes=["z"])
    assert lonely.max_flow("a", "z").value == 0


def test_k_shortest_paths():
    g = tc.Graph([("a", "b", 1), ("b", "d", 1), ("a", "c", 1), ("c", "d", 2), ("a", "d", 5)])
    assert g.k_shortest_paths("a", "d", k=3, weight="weight") == [
        ["a", "b", "d"], ["a", "c", "d"], ["a", "d"]]
    assert g.k_shortest_paths("a", "d", k=1) == [["a", "d"]]
    assert len(g.k_shortest_paths("a", "d", k=10)) == 3  # every loopless route there is
    with pytest.raises(tc.NoPath):
        tc.Graph([("a", "b"), ("c", "d")]).k_shortest_paths("a", "d")


def test_betweenness_engines():
    g = tc.scale_free_graph(300, 2, seed=5)
    with pytest.raises(tc.TarecoError):
        g.betweenness(engine="gpu")
    pytest.importorskip("igraph")
    for graph in (g, g.to_directed()):
        python = graph.betweenness(engine="python")
        fast = graph.betweenness(engine="igraph")
        for n in graph:
            assert fast[n] == pytest.approx(python[n], abs=1e-9)
    weighted = tc.Graph([(u, v, random.Random(u * 7 + v).randint(1, 5)) for u, v in g.edges])
    assert weighted.betweenness(engine="igraph", weight="weight") == pytest.approx(
        weighted.betweenness(engine="python", weight="weight"))
    raw_py = g.betweenness(engine="python", normalized=False)
    raw_ig = g.betweenness(engine="igraph", normalized=False)
    assert raw_ig == pytest.approx(raw_py)


nx = pytest.importorskip("networkx")


@pytest.mark.parametrize("seed", range(5))
@pytest.mark.parametrize("directed", [True, False])
def test_flow_matches_networkx(seed, directed):
    rng = random.Random(seed)
    g = tc.random_graph(30, 0.15, directed=directed, seed=seed)
    for u, v in list(g.edges):
        g.edges[u, v]["weight"] = rng.randint(1, 9)
    G = g.to_networkx()
    for s, t in [(0, 29), (3, 17), (10, 2)]:
        ours = g.max_flow(s, t)
        assert ours.value == nx.maximum_flow_value(G, s, t, capacity="weight")
        assert sum(c for _, _, c in ours.cut) == ours.value


@pytest.mark.parametrize("seed", range(4))
def test_k_shortest_matches_networkx(seed):
    rng = random.Random(seed)
    g = tc.random_graph(25, 0.2, directed=True, seed=seed)
    for u, v in list(g.edges):
        g.edges[u, v]["weight"] = rng.randint(1, 9)
    G = g.to_networkx()
    try:
        expected = []
        for path in nx.shortest_simple_paths(G, 0, 24, weight="weight"):
            expected.append(nx.path_weight(G, path, "weight"))
            if len(expected) == 6:
                break
    except nx.NetworkXNoPath:
        with pytest.raises(tc.NoPath):
            g.k_shortest_paths(0, 24, k=6)
        return
    ours = [sum(g.edges[a, b]["weight"] for a, b in zip(p, p[1:]))
            for p in g.k_shortest_paths(0, 24, k=6, weight="weight")]
    assert ours == expected

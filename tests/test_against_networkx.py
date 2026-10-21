"""Cross-check the from-scratch algorithms against networkx, when it is installed."""

import random

import pytest

import tareco as tc

nx = pytest.importorskip("networkx")


def pairs(seed, directed=False, weighted=False, n=40, p=0.12):
    rng = random.Random(seed)
    g = tc.random_graph(n, p, directed=directed, seed=seed)
    if weighted:
        for u, v in list(g.edges):
            g.edges[u, v]["weight"] = rng.randint(1, 9)
    return g, g.to_networkx()


def close(a, b, tol=1e-6):
    assert a.keys() == b.keys()
    for k in a:
        assert a[k] == pytest.approx(b[k], abs=tol), k


@pytest.mark.parametrize("seed", range(4))
@pytest.mark.parametrize("directed", [False, True])
def test_centralities_match(seed, directed):
    g, G = pairs(seed, directed=directed, weighted=True)
    close(g.pagerank(), nx.pagerank(G, tol=1e-12, max_iter=1000), 1e-6)
    close(g.betweenness(), nx.betweenness_centrality(G))
    close(g.betweenness(weight="weight"), nx.betweenness_centrality(G, weight="weight"))
    close(g.betweenness(normalized=False), nx.betweenness_centrality(G, normalized=False))
    reverse = G.reverse() if directed else G  # networkx measures incoming distance
    close(g.closeness(), nx.closeness_centrality(reverse))
    close(g.degree_centrality(), nx.degree_centrality(G))


@pytest.mark.parametrize("seed", range(4))
def test_structure_matches(seed):
    g, G = pairs(seed, weighted=True)
    close(g.clustering(), nx.clustering(G))
    assert g.triangles() == nx.triangles(G)
    assert g.core_number() == nx.core_number(G)
    assert g.transitivity() == pytest.approx(nx.transitivity(G))
    assert g.density() == pytest.approx(nx.density(G))
    mst = g.spanning_tree()
    nx_mst = nx.minimum_spanning_tree(G)
    assert sum(d["weight"] for _, d in mst.edges.items()) == nx_mst.size(weight="weight")
    assert sorted(map(sorted, g.components())) == sorted(map(sorted, nx.connected_components(G)))


@pytest.mark.parametrize("seed", range(4))
def test_paths_match(seed):
    g, G = pairs(seed, directed=True, weighted=True, p=0.08)
    for s in list(g)[:8]:
        assert g.distances(s) == nx.single_source_shortest_path_length(G, s)
        assert g.distances(s, weight="weight") == nx.single_source_dijkstra_path_length(G, s)
    ours = sorted(map(sorted, g.strong_components()))
    assert ours == sorted(map(sorted, nx.strongly_connected_components(G)))


@pytest.mark.parametrize("seed", range(4))
def test_louvain_quality(seed):
    g = tc.community_graph([25, 20, 15, 10], p_in=0.3, p_out=0.03, seed=seed)
    G = g.to_networkx()
    ours = g.communities()
    q_ours = g.modularity(ours)
    assert q_ours == pytest.approx(nx.community.modularity(G, ours))
    q_nx = nx.community.modularity(G, nx.community.louvain_communities(G, seed=seed))
    assert q_ours >= q_nx - 0.02

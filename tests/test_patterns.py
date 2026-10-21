import pytest

import tareco as tc
from tareco import patterns as pat


def flows():
    g = tc.Graph(directed=True)
    g.add_edges([("a", "b", 100), ("b", "c", 80), ("c", "a", 90),         # loop, bottleneck 80
                 ("c", "d", 5), ("d", "e", 5), ("e", "f", 5), ("f", "g", 5),  # chain d, e, f
                 ("x", "y", 50), ("y", "x", 48)])                          # back and forth
    for i in range(6):
        g.add_edge(f"in{i}", "relay", weight=10)
        g.add_edge("relay", f"out{i}", weight=10)
        g.add_edge(f"s{i}", "sink", weight=1)
        g.add_edge("source", f"t{i}", weight=1)
    return g


def test_every_kind_on_a_directed_flow():
    found = flows().patterns()
    kinds = [p.kind for p in found]
    for kind in ("cycle", "pass_through", "fan_in", "fan_out", "chain", "back_and_forth", "star"):
        assert kind in kinds, kind
    cycle = found.of("cycle")[0]
    assert set(cycle.nodes) == {"a", "b", "c"} and cycle.details["bottleneck"] == 80
    assert cycle.text.endswith("Up to 80 can go all the way around.")
    assert found.of("chain")[0].nodes == ["c", "d", "e", "f", "g"]
    assert found.of("pass_through")[0].nodes[0] == "relay"
    assert found.of("fan_in")[0].text == "sink receives from 6 nodes, 6 of which send to nobody else, and sends to none."
    assert found.of("fan_out")[0].text == "source sends to 6 nodes, 6 of which hear from nobody else, and receives from none."
    assert found.of("back_and_forth")[0].details == {"there": 50, "back": 48}


def test_cycles_respect_length_and_rank_by_bottleneck():
    g = tc.Graph(directed=True)
    g.add_edges([(1, 2, 5), (2, 3, 5), (3, 1, 5),           # bottleneck 5
                 (4, 5, 9), (5, 6, 9), (6, 7, 9), (7, 4, 9),  # length 4, bottleneck 9
                 (8, 9, 1), (9, 10, 1), (10, 11, 1), (11, 12, 1), (12, 8, 1)])  # length 5
    cycles = g.patterns(kinds=["cycle"])
    assert [len(c.nodes) for c in cycles] == [4, 3]
    assert len(g.patterns(kinds=["cycle"], max_cycle=5)) == 3
    assert g.patterns(kinds=["cycle"], limit=1)[0].details["bottleneck"] == 9
    unweighted = tc.Graph([(1, 2), (2, 3), (3, 1)], directed=True)
    assert "can go all the way around" not in unweighted.patterns()[0].text


def test_closed_loops_of_intermediaries_are_not_chains():
    ring = tc.cycle_graph(6, directed=True)
    assert not ring.patterns(kinds=["chain"])
    assert len(ring.patterns(kinds=["cycle"], max_cycle=6)) == 1


def test_unweighted_relay_and_min_fan():
    g = tc.Graph(directed=True)
    for i in range(4):
        g.add_edge(f"a{i}", "hub")
        g.add_edge("hub", f"b{i}")
    assert not g.patterns(kinds=["pass_through"])
    relay = g.patterns(kinds=["pass_through"], min_fan=4)[0]
    assert relay.text == "hub receives from 4 nodes and passes on to 4."


def test_undirected_graphs_get_stars_and_cliques_only():
    g = tc.complete_graph(6)
    for i in range(10):
        g.add_edge(0, f"leaf{i}")
    found = g.patterns()
    assert {p.kind for p in found} == {"clique", "star"}
    assert found.of("clique")[0].details["size"] == 6
    assert found.of("star")[0].text == "0 is the only connection of 10 nodes."


def test_cliques_match_networkx():
    nx = pytest.importorskip("networkx")
    g = tc.random_graph(60, 0.25, seed=4)
    ours = {frozenset(p.nodes) for p in g.patterns(kinds=["clique"], limit=10_000)}
    theirs = {frozenset(c) for c in nx.find_cliques(g.to_networkx()) if len(c) >= 4}
    assert ours == theirs


def test_language_labels_and_errors():
    g = flows()
    for n in g:
        g.nodes[n]["name"] = str(n).upper()
    pt = g.patterns(lang="pt", label="name")
    assert pt.of("cycle")[0].text.startswith("A, B e C formam um ciclo: A para B para C para A.")
    with pytest.raises(tc.TarecoError, match="unknown pattern kinds"):
        g.patterns(kinds=["spiral"])
    assert repr(tc.Graph().patterns()) == "(no patterns)"


def test_patterns_table():
    pytest.importorskip("pandas")
    df = flows().patterns().to_pandas()
    assert {"kind", "score", "nodes", "text"} <= set(df.columns)


def test_search_budget_keeps_big_graphs_fast(monkeypatch):
    monkeypatch.setattr(pat, "STEP_BUDGET", 50)
    g = tc.random_graph(200, 0.05, directed=True, seed=1)
    assert isinstance(g.patterns(kinds=["cycle", "clique"]), pat.Patterns)


def test_explain_mentions_patterns():
    text = str(flows().explain())
    assert "a, b and c form a loop" in text
    assert "relay receives from 6 nodes and passes almost all of it on to 6" in text

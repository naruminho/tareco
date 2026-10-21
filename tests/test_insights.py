import os
import random

import pytest

import tareco as tc
from tareco import i18n

HERE = os.path.dirname(os.path.abspath(__file__))
EXAMPLES = os.path.join(os.path.dirname(HERE), "examples")


def friends():
    return tc.Graph(os.path.join(EXAMPLES, "friends.csv"), nodes=os.path.join(EXAMPLES, "people.csv"))


def planted(seed=1):
    """Three groups; each lives mostly in one city, and group 0 is much richer."""
    rng = random.Random(seed)
    g = tc.community_graph([40, 40, 40], p_in=0.3, p_out=0.01, seed=seed)
    cities = ["Recife", "Curitiba", "Manaus"]
    for n, attrs in g.nodes.items():
        grp = attrs["group"]
        attrs["city"] = cities[grp] if rng.random() < 0.85 else rng.choice(cities)
        attrs["balance"] = rng.uniform(8000, 12000) if grp == 0 else rng.uniform(1000, 3000)
        attrs["name"] = f"client-{n}"
    return g


# ------------------------------------------------------------------- profiles

def test_profiles_find_what_sets_each_group_apart():
    g = planted()
    profiles = g.profile()
    assert len(profiles) == 3 and [p.size for p in profiles] == sorted((p.size for p in profiles), reverse=True)
    by_city = {}
    for p in profiles:
        city = next(t for t in p.traits if t.attribute == "city")
        assert city.kind == "category" and city.group_value >= 0.7 and city.overall_value < 0.5
        by_city[city.value] = p
    assert set(by_city) == {"Recife", "Curitiba", "Manaus"}
    rich = by_city["Recife"]
    balance = next(t for t in rich.traits if t.attribute == "balance")
    assert balance.kind == "number" and balance.group_value > 3 * balance.overall_value / 2
    assert "balance higher" in balance.short("en")
    assert all(t.attribute not in ("name", "group") or t.attribute == "group" for p in profiles for t in p.traits)
    assert not any(t.attribute == "name" for p in profiles for t in p.traits)  # ids are not traits


def test_profile_details_and_text():
    p = planted().profile()[0]
    assert len(p.key_members) == 3 and 0.5 < p.inward <= 1 and p.linked is not None
    text = repr(p)
    assert text.startswith("Group 1 - ") and "key members:" in text and "(vs " in text
    assert p.to_dict()["size"] == p.size
    pt = planted().profile(lang="pt")[0]
    assert repr(pt).startswith("Grupo 1 - ") and "principais membros:" in repr(pt)


def test_profile_by_attribute_dict_and_sets():
    g = planted()
    by_city = g.profile(groups="city")
    assert {p.label for p in by_city} == {"Recife", "Curitiba", "Manaus"}
    assert not any(t.attribute == "city" for p in by_city for t in p.traits)
    halves = g.profile(groups={n: ("low" if n < 60 else "high") for n in g})
    assert [p.size for p in halves] == [60, 60]
    sets = g.profile(groups=[set(range(10)), set(range(10, 120))])
    assert [p.size for p in sets] == [110, 10]


def test_profiles_to_pandas():
    pytest.importorskip("pandas")
    df = planted().profile().to_pandas()
    assert list(df.columns[:3]) == ["group", "size", "share"] and len(df) == 3


# -------------------------------------------------------------------- explain

def test_explain_friends():
    e = friends().explain(weight="messages")
    text = str(e)
    assert text.startswith("What this network shows")
    kinds = [f.kind for f in e]
    assert kinds[:3] == ["overview", "connected", "groups"]
    assert kinds.count("group") == 4
    assert "city: Recife in 75% (vs 19% overall)" in text
    assert "Iris is a bridge between groups" in text
    assert "The strongest connection is Ana and Bia (42)." in text
    for f in e:
        assert all(n in friends() for n in f.nodes)
    assert e._repr_markdown_().startswith("**What this network shows**")
    assert e.to_dict()[0]["kind"] == "overview"


def test_explain_in_portuguese():
    text = str(friends().explain(lang="pt", weight="messages"))
    assert text.startswith("O que esta rede mostra")
    assert "16 nós e 31 conexões; em média cada nó se conecta a 3,9 outros." in text
    assert "Grupo 1 (4 nós, 25%): city: Recife em 75% (contra 19% no geral)." in text
    assert "Iris é uma ponte entre grupos" in text


def test_explain_disconnected_and_isolated():
    g = tc.Graph([("a", "b"), ("b", "c"), ("c", "a"), ("x", "y")], nodes=["lonely"])
    text = str(g.explain())
    assert "split into 3 separate parts; the largest holds 50%" in text
    assert "1 node has no connections at all." in text
    assert "1 small island of 2 or 3 nodes is cut off" in text
    pt = str(g.explain(lang="pt"))
    assert "1 nó não tem nenhuma conexão." in pt and "1 ilha pequena" in pt


def test_explain_without_groups():
    text = str(tc.random_graph(80, 0.2, seed=3).explain())
    assert "There are no clear groups" in text


def test_explain_loose_groups_are_called_so():
    g = tc.community_graph([30, 30], p_in=0.15, p_out=0.3, seed=2)  # more links across than inside
    e = g.explain(groups="group")
    assert "most connections" in str(e) and "cross from one group to another" in str(e)


def test_explain_hubs_and_flows():
    g = tc.Graph(directed=True)
    for i in range(40):
        g.add_edge(f"s{i}", "mule")
        g.add_edge(f"s{i}", f"s{(i + 1) % 40}")
    for i in range(8):
        g.add_edge("boss", f"t{i}")
    g.add_edge("mule", "boss")
    text = str(g.explain())
    assert "mule receives from 40 nodes but sends to 1." in text
    assert "boss sends to 8 nodes but receives from 1." in text
    assert "mule has" in text and "more connections than a typical node" in text
    assert "of the links go both ways." in text


def test_explain_weights_only_when_notable():
    even = tc.Graph([(i, i + 1, 10) for i in range(30)])
    assert not [f for f in even.explain() if f.kind == "concentration"]
    skewed = tc.Graph([(i, i + 1, 1000 if i < 3 else 1) for i in range(30)])
    concentration = [f for f in skewed.explain() if f.kind == "concentration"]
    assert concentration and "carry 9" in concentration[0].text


def test_explain_uses_labels_and_handles_empty_graphs():
    g = tc.Graph([(1, 2), (2, 3)], nodes={1: {"name": "Ana"}, 2: {"name": "Bia"}, 3: {"name": "Caio"}})
    assert "The most important nodes are Bia" in str(g.explain(label="name"))
    assert len(tc.Graph().explain()) == 0
    assert [f.kind for f in tc.Graph(["a"]).explain()] == ["overview", "connected"]


# ------------------------------------------------------------------- language

def test_language_setting(monkeypatch):
    monkeypatch.setattr(i18n, "_default", None)
    monkeypatch.setenv("TARECO_LANG", "pt_BR")
    assert i18n.get_language() == "pt"
    monkeypatch.delenv("TARECO_LANG")
    assert i18n.get_language() == "en"
    tc.set_language("PT")
    assert i18n.get_language() == "pt" and i18n.get_language("en") == "en"
    assert str(friends().explain()).startswith("O que esta rede mostra")
    with pytest.raises(tc.TarecoError):
        tc.set_language("fr")


def test_number_formats():
    assert i18n.number(1234567, "en") == "1,234,567" and i18n.number(1234567, "pt") == "1.234.567"
    assert i18n.number(3.875, "pt") == "3,9" and i18n.number(0.034, "en") == "0.03"
    assert i18n.percent(0.25, "pt") == "25%" and i18n.percent(0.002, "pt") == "0,2%"
    assert i18n.join(["a", "b", "c"], "pt") == "a, b e c"

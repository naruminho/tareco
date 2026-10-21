import json
import os
import re

import tareco as tc
from tareco.viz import build_payload, build_webgl_payload, to_html

HERE = os.path.dirname(os.path.abspath(__file__))
EXAMPLES = os.path.join(os.path.dirname(HERE), "examples")


def friends():
    return tc.Graph(os.path.join(EXAMPLES, "friends.csv"), nodes=os.path.join(EXAMPLES, "people.csv"))


def payload_from_html(page):
    return json.loads(re.search(r"window\.__TARECO__ = (.*?);</script>", page, re.S).group(1))


def test_insights_travel_with_the_view():
    p = build_payload(friends())
    findings = p["config"]["insights"]
    assert findings[0]["kind"] == "overview"
    n = len(p["nodes"])
    for f in findings:
        assert all(0 <= i < n for i in f["nodes"])
    groups = [f for f in findings if f["kind"] == "group"]
    assert len(groups) == 4 and {f["group"] for f in groups} == {"1", "2", "3", "4"}
    assert build_payload(friends(), insights=False)["config"]["insights"] == []


def test_legend_notes_describe_each_group():
    items = build_payload(friends())["config"]["legend"]["items"]
    assert {it["note"] for it in items} == {"Recife 75%", "São Paulo 75%", "Curitiba 75%", "Salvador 75%"}
    by_city = build_payload(friends(), color="city")["config"]["legend"]["items"]
    assert all("note" not in it or isinstance(it["note"], str) for it in by_city)


def test_portuguese_view():
    p = build_payload(friends(), lang="pt")
    config = p["config"]
    assert config["lang"] == "pt"
    assert config["legend"]["title"] == "comunidade" and config["legend"]["metric"] == "community"
    assert "grau" in p["nodes"][0]["metrics"]
    assert config["insights"][0]["text"].startswith("16 nós e 31 conexões")
    page = to_html(friends(), lang="pt")
    assert "tarecoText" in page and all(ord(c) < 128 for c in page)


def test_webgl_groups_carry_keys_and_notes():
    p = build_webgl_payload(friends(), lang="pt")
    groups = p["groups"]
    assert groups["key"] == ["1", "2", "3", "4"]
    assert groups["label"] == ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]
    assert all(note and note.endswith("75%") for note in groups["note"])
    assert p["config"]["groupName"] == "comunidade"
    assert {f["group"] for f in p["config"]["insights"] if f["kind"] == "group"} <= set(groups["key"])


def test_trimmed_views_keep_insights_about_the_whole_graph():
    g = tc.scale_free_graph(3000, 2, seed=1)
    p = payload_from_html(to_html(g, max_nodes=300))
    overview = p["config"]["insights"][0]["text"]
    assert overview.startswith("3,000 nodes")
    assert all(0 <= i < 300 for f in p["config"]["insights"] for i in f["nodes"])

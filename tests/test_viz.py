import json
import re

import pytest

import tareco as tc
from tareco.viz import GRADIENT, LIB_3D, PALETTE, build_payload, notebook_html, to_html


def payload_from_html(page):
    m = re.search(r"window\.__TARECO__ = (.*?);</script>", page, re.S)
    return json.loads(m.group(1))


def test_html_is_standalone_and_offline():
    page = to_html(tc.path_graph(3), title="Hello <b>")
    assert page.startswith("<!doctype html>")
    assert "<title>Hello &lt;b&gt;</title>" in page
    assert "force-graph" in page and "ForceGraph" in page
    assert "<script src=" not in page and "<link" not in page
    for marker in ("__TITLE__", "<!--LIB-->", "/*DATA*/", "/*STYLE*/", "/*APP*/"):
        assert marker not in page
    assert payload_from_html(page)["config"]["title"] == "Hello <b>"


def test_attribute_text_cannot_break_out_of_the_script():
    g = tc.Graph()
    g.add_node("x</script><script>alert(1)</script>", note="/*APP*/ <!--LIB-->")
    page = to_html(g)
    assert page.count("</script>") == 3  # lib, data and app blocks only
    data = payload_from_html(page)
    assert data["nodes"][0]["label"].startswith("x</script>")
    assert data["nodes"][0]["attrs"]["note"] == "/*APP*/ <!--LIB-->"


def test_3d_uses_cdn_library():
    page = to_html(tc.path_graph(3), dim=3)
    assert LIB_3D in page and "ForceGraph()" in page  # app handles both
    with pytest.raises(tc.TarecoError):
        to_html(tc.path_graph(3), dim=4)


def test_default_color_is_community_and_size_pagerank():
    g = tc.Graph([("a", "b"), ("b", "c"), ("c", "a"), ("c", "d"), ("d", "e"), ("e", "f"), ("f", "d")])
    p = build_payload(g)
    legend = p["config"]["legend"]
    assert legend["kind"] == "category" and legend["title"] == "community"
    assert [it["label"] for it in legend["items"]] == ["1", "2"]
    assert {n["color"] for n in p["nodes"]} == {PALETTE[0], PALETTE[1]}
    assert p["config"]["size"] == "pagerank"
    assert all("pagerank" in n["metrics"] and "degree" in n["metrics"] for n in p["nodes"])
    sizes = [n["val"] for n in p["nodes"]]
    assert min(sizes) >= 1.5 and max(sizes) <= 18


def test_graph_without_edges_gets_plain_style():
    p = build_payload(tc.Graph(["a", "b"]))
    assert p["config"]["legend"] is None and p["config"]["size"] is None
    assert {n["val"] for n in p["nodes"]} == {4.0}


def test_numeric_attribute_gets_a_scale():
    g = tc.Graph([("a", "b"), ("b", "c")], nodes={"a": {"age": 10.5}, "b": {"age": 30.0}})
    p = build_payload(g, color="age")
    legend = p["config"]["legend"]
    assert legend["kind"] == "scale" and legend["min"] == 10.5 and legend["max"] == 30.0
    colors = {n["label"]: n["color"] for n in p["nodes"]}
    assert colors["a"] == GRADIENT[0] and colors["b"] == GRADIENT[-1]
    assert colors["c"] == "#94a3b8"  # missing value


def test_small_integer_attribute_is_categorical():
    g = tc.community_graph([5, 5, 5], seed=1)
    legend = build_payload(g, color="group")["config"]["legend"]
    assert legend["kind"] == "category" and len(legend["items"]) == 3


def test_text_attribute_categories_ordered_by_frequency_with_missing():
    g = tc.Graph([("a", "b"), ("b", "c"), ("c", "d")],
                 nodes={"a": {"team": "red"}, "b": {"team": "blue"}, "c": {"team": "blue"}})
    p = build_payload(g, color="team")
    items = p["config"]["legend"]["items"]
    assert [(i["label"], i["count"]) for i in items[:2]] == [("blue", 2), ("red", 1)]
    assert items[-1].get("missing") and items[-1]["count"] == 1
    assert [n["group"] for n in p["nodes"]] == ["red", "blue", "blue", ""]


def test_color_and_size_accept_dicts_functions_and_constants():
    g = tc.star_graph(3)
    p = build_payload(g, color=g.betweenness(), size=lambda n: 10 if n == 0 else 1)
    assert p["config"]["legend"]["kind"] == "scale"
    vals = [n["val"] for n in p["nodes"]]
    assert vals[0] == 18 and vals[1] == 1.5
    p = build_payload(g, color="#ff0000", size=7)
    assert {n["color"] for n in p["nodes"]} == {"#ff0000"} and {n["val"] for n in p["nodes"]} == {7.0}
    with pytest.raises(tc.TarecoError):
        build_payload(g, color=3.5)


def test_many_categories_get_generated_colors():
    g = tc.Graph([(i, i + 100) for i in range(20)], nodes={i: {"k": f"c{i}"} for i in range(20)})
    items = build_payload(g, color="k")["config"]["legend"]["items"]
    assert len({i["color"] for i in items}) == len(items)


def test_labels_edges_and_curves():
    g = tc.Graph([("a", "b", 1), ("b", "a", 5), ("b", "b", 2)], directed=True,
                 nodes={"a": {"name": "Ana"}})
    p = build_payload(g, label="name")
    assert [n["label"] for n in p["nodes"]] == ["Ana", "b"]
    widths = {(l["source"], l["target"]): l for l in p["links"]}
    assert widths[(0, 1)]["w"] == 0.6 and widths[(1, 0)]["w"] == 5.0
    assert widths[(0, 1)]["curve"] > 0 and widths[(1, 1)]["curve"] > widths[(0, 1)]["curve"]
    assert p["config"]["directed"] and "in" in p["nodes"][0]["metrics"]
    plain = build_payload(tc.path_graph(3))
    assert {l["w"] for l in plain["links"]} == {1.0}


def test_notebook_iframe_and_repr():
    frame = notebook_html(tc.path_graph(3), height=300)
    assert frame.startswith('<iframe srcdoc="&lt;!doctype html&gt;')
    assert "height:300px" in frame
    assert tc.Graph()._repr_html_() is None
    assert tc.path_graph(3)._repr_html_().startswith("<iframe")


def test_save_and_top_level_helpers(tmp_path):
    out = tmp_path / "g.html"
    path = tc.save([("a", "b")], str(out), title="t", color="degree")
    assert out.exists() and path == str(out.resolve())
    assert payload_from_html(out.read_text(encoding="utf-8"))["config"]["legend"]["kind"] == "scale"


def test_show_opens_a_browser(monkeypatch):
    opened = []
    monkeypatch.setattr("webbrowser.open", opened.append)
    tc.show([("a", "b")], directed=True, title="x")
    assert len(opened) == 1 and opened[0].startswith("file://") and opened[0].endswith(".html")

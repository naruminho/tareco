"""Big graphs: renderer choice, trimming, the group overview, size budgets and notebooks."""

import json
import re
import sys

import pytest

import tareco as tc
from tareco import viz
from tareco.viz import build_webgl_payload, notebook_html, to_html


def payload_from_html(page):
    m = re.search(r"window\.__TARECO__ = (.*?);</script>", page, re.S)
    return json.loads(m.group(1))


def big(n=3000, m=2, seed=1):
    return tc.scale_free_graph(n, m, seed=seed)


def test_renderer_choice():
    assert payload_from_html(to_html(tc.path_graph(10)))["config"]["renderer"] == "canvas"
    page = to_html(big())
    assert payload_from_html(page)["config"]["renderer"] == "webgl"
    assert "graphology" in page and "Sigma" in page and "tarecoLayout" in page
    assert "ForceGraph" not in page
    assert payload_from_html(to_html(tc.path_graph(10), renderer="webgl"))["config"]["renderer"] == "webgl"
    assert payload_from_html(to_html(big(), renderer="canvas"))["config"]["renderer"] == "canvas"
    with pytest.raises(tc.TarecoError):
        to_html(tc.path_graph(3), renderer="svg")
    with pytest.raises(tc.TarecoError):
        to_html(tc.path_graph(3), renderer="webgl", dim=3)


def test_webgl_payload_is_consistent():
    g = big(2500)
    g.add_edge(5, 5)  # self-loop: kept in the graph, not drawn
    p = build_webgl_payload(g)
    nodes, edges, groups = p["nodes"], p["edges"], p["groups"]
    n = len(nodes["label"])
    assert n == 2500
    for column in ("c", "size", "x", "y", "cat", "grp"):
        assert len(nodes[column]) == n
    assert all(len(values) == n for values in nodes["metrics"].values())
    flat = edges["e"]
    assert len(flat) % 2 == 0 and len(flat) // 2 == g.edge_count - 1
    assert all(0 <= i < n for i in flat)
    assert all(0 <= c < len(nodes["colors"]) for c in nodes["c"])
    assert sum(groups["size"]) == len(g) and sum(groups["shown"]) == n
    assert all(0 <= gi < len(groups["label"]) for gi in nodes["grp"])
    legend = p["config"]["legend"]
    assert all(0 <= k < len(legend["items"]) for k in nodes["cat"])
    assert len(groups["e"]) == 2 * len(groups["w"])
    assert p["config"]["groupTitle"] == "community"
    assert groups["label"][0].startswith("Community ")
    assert build_webgl_payload(g) == p  # seeded, so repeatable


def test_trimming_keeps_the_most_important_nodes():
    g = big(3000)
    rank = g.pagerank()
    top = set(sorted(rank, key=rank.get, reverse=True)[:500])
    p = payload_from_html(to_html(g, max_nodes=500))
    kept = set(int(label) for label in p["nodes"]["label"])
    assert kept == top
    config = p["config"]
    assert config["counts"]["nodes"] == 500 and config["total"]["nodes"] == 3000
    assert sum(p["groups"]["size"]) == 3000  # the overview still describes everything


def test_edge_cap_keeps_the_heaviest_edges():
    g = tc.Graph()
    for i in range(300):
        g.add_edge(i, (i + 1) % 300, weight=i)
    p = build_webgl_payload(g, *viz._reduce(g, 1000, 10, viz._metric_cache(g)))
    flat = p["edges"]["e"]
    labels = p["nodes"]["label"]
    kept = {frozenset((int(labels[flat[k]]), int(labels[flat[k + 1]]))) for k in range(0, len(flat), 2)}
    assert kept == {frozenset((i, (i + 1) % 300)) for i in range(290, 300)}


def test_canvas_view_is_trimmed_too():
    p = payload_from_html(to_html(big(5000), renderer="canvas"))
    assert len(p["nodes"]) == 3000 and p["config"]["total"]["nodes"] == 5000


def test_overview_starts_above_threshold(monkeypatch):
    monkeypatch.setattr(viz, "OVERVIEW_START", (1000, 10**9))
    assert build_webgl_payload(big(2500))["config"]["start"] == "overview"
    assert build_webgl_payload(big(900))["config"]["start"] == "nodes"


def test_small_groups_are_merged_in_the_overview(monkeypatch):
    monkeypatch.setattr(viz, "MAX_GROUPS", 5)
    g = tc.Graph([(i, i + 1000) for i in range(40)])  # 40 components
    groups = build_webgl_payload(g, color="component")["groups"]
    assert len(groups["label"]) == 6
    assert groups["label"][-1] == "35 smaller groups"
    assert sum(groups["size"]) == 80


def test_overview_follows_a_categorical_color():
    g = big(2500)
    for n in g:
        g.nodes[n]["team"] = "abc"[n % 3]
    p = build_webgl_payload(g, color="team")
    assert sorted(p["groups"]["label"]) == ["a", "b", "c"]
    assert p["config"]["groupTitle"] == "team"
    legend_colors = {it["label"]: it["color"] for it in p["config"]["legend"]["items"]}
    assert dict(zip(p["groups"]["label"], p["groups"]["color"])) == legend_colors


def test_colors_past_the_palette_are_hex():
    g = tc.Graph([(i, i + 100) for i in range(30)], nodes={i: {"k": f"c{i}"} for i in range(30)})
    items = build_webgl_payload(g, color="k")["config"]["legend"]["items"]
    assert all(re.fullmatch(r"#[0-9a-f]{6}", it["color"]) for it in items)


def test_budget_shrinks_the_page():
    g = big(4000)
    full = notebook_html(g, budget_mb=100)
    small = notebook_html(g, budget_mb=0.55)
    assert len(full.encode()) > 0.55e6 >= len(small.encode())
    inner = small[small.index('srcdoc="') + 8:]
    import html as html_lib
    p = payload_from_html(html_lib.unescape(inner[:inner.index('" style=')]))
    assert p["config"]["counts"]["nodes"] < 4000 and p["config"]["total"]["nodes"] == 4000


def test_pages_are_plain_ascii():
    g = tc.Graph([("João", "Ação"), ("Ação", "Zoë")], title="Transferências")
    for page in (to_html(g), to_html(g, renderer="webgl"), notebook_html(g)):
        assert all(ord(ch) < 128 for ch in page)
    data = payload_from_html(to_html(g, renderer="webgl"))
    assert data["nodes"]["label"] == ["João", "Ação", "Zoë"]
    assert "<title>Transfer&#234;ncias</title>" in to_html(g)


def test_slow_metrics_are_guarded(monkeypatch):
    monkeypatch.setattr(viz, "CLOSENESS_LIMIT", 100)
    with pytest.raises(tc.TarecoError, match="closeness"):
        to_html(big(500), color="closeness")
    monkeypatch.setattr(viz, "SAMPLED_BETWEENNESS", (100, 20))
    p = payload_from_html(to_html(big(500), color="betweenness"))
    assert p["config"]["legend"]["kind"] == "scale"


def test_repr_html_uses_webgl_for_big_graphs():
    frame = big(2500)._repr_html_()
    assert "<iframe srcdoc=" in frame and "sigma" in frame


# --------------------------------------------------------------- environments

def test_show_on_databricks_uses_displayHTML(monkeypatch):
    shown = []
    monkeypatch.setenv("DATABRICKS_RUNTIME_VERSION", "17.3")
    monkeypatch.setattr(sys.modules["__main__"], "displayHTML", shown.append, raising=False)
    monkeypatch.setattr("webbrowser.open", lambda url: pytest.fail("no browser on a cluster"))
    tc.Graph([("a", "b")]).show(title="dbx")
    assert len(shown) == 1 and "<iframe srcdoc=" in shown[0]
    assert viz.default_budget_mb() == viz.DATABRICKS_BUDGET_MB


def test_databricks_job_without_display_prints_the_file(monkeypatch, capsys):
    monkeypatch.setenv("DATABRICKS_RUNTIME_VERSION", "17.3")
    monkeypatch.delattr(sys.modules["__main__"], "displayHTML", raising=False)
    monkeypatch.setattr(viz, "_ipython", lambda: None)
    monkeypatch.setattr("webbrowser.open", lambda url: pytest.fail("no browser on a cluster"))
    tc.Graph([("a", "b")]).show()
    assert "saved to" in capsys.readouterr().out


def test_headless_machine_prints_the_file(monkeypatch, capsys):
    monkeypatch.delenv("DATABRICKS_RUNTIME_VERSION", raising=False)
    monkeypatch.setattr(viz, "_ipython", lambda: None)
    monkeypatch.setattr("webbrowser.open", lambda url: False)
    tc.Graph([("a", "b")]).show()
    out = capsys.readouterr().out
    assert "no browser here" in out and out.strip().endswith(".html")


def test_jupyter_kernel_gets_inline_html(monkeypatch):
    displayed = []

    class Kernel:
        kernel = object()
        user_ns = {}

    monkeypatch.delenv("DATABRICKS_RUNTIME_VERSION", raising=False)
    monkeypatch.delattr(sys.modules["__main__"], "displayHTML", raising=False)
    monkeypatch.setattr(viz, "_ipython", lambda: Kernel())
    ipython_display = pytest.importorskip("IPython.display")
    monkeypatch.setattr(ipython_display, "display", lambda obj: displayed.append(obj.data))
    monkeypatch.setattr("webbrowser.open", lambda url: pytest.fail("notebooks render inline"))
    tc.Graph([("a", "b")]).show()
    assert len(displayed) == 1 and "<iframe srcdoc=" in displayed[0]

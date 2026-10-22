import datetime as dt
import json
import random
import re

import pytest

import tareco as tc
from tareco import temporal as tl_module


def story(directed=False):
    """Six months of messages; a second crowd joins in April and someone gets very popular in May."""
    rng = random.Random(2)
    people = [f"p{i}" for i in range(60)]
    rows = []
    for month in range(1, 7):
        for _ in range(40 + month * 15):
            a, b = rng.sample(people[:30] if month < 4 else people, 2)
            rows.append({"sender": a, "receiver": b, "when": f"2026-{month:02d}-{rng.randint(1, 28):02d}"})
        if month == 5:
            rows += [{"sender": f"p{i}", "receiver": "star", "when": "2026-05-10"} for i in range(25)]
    return tc.timeline(rows, time="when", directed=directed)


# --------------------------------------------------------------------- times

def test_time_formats():
    parse = tl_module._parse_times
    assert parse(["2026-03-01", "2026-03-01T10:30:00", "2026-03-02Z"], None)[1] == dt.datetime(2026, 3, 1, 10, 30)
    assert parse([dt.date(2026, 1, 5)], None) == [dt.datetime(2026, 1, 5)]
    aware = dt.datetime(2026, 1, 5, 12, tzinfo=dt.timezone(dt.timedelta(hours=-3)))
    assert parse([aware], None) == [dt.datetime(2026, 1, 5, 15)]
    assert parse(["25/12/2026", "01/02/2026"], None) == [dt.datetime(2026, 12, 25), dt.datetime(2026, 2, 1)]
    assert parse(["12/25/2026", "02/01/2026"], None) == [dt.datetime(2026, 12, 25), dt.datetime(2026, 2, 1)]
    assert parse(["2026/03/09 08:15"], None) == [dt.datetime(2026, 3, 9, 8, 15)]
    with pytest.raises(tc.TarecoError, match="ambiguous"):
        parse(["01/02/2026", "03/04/2026"], None)
    assert parse(["01/02/2026"], True) == [dt.datetime(2026, 2, 1)]
    assert parse([1, 2.5, 3], None) == [1, 2.5, 3]
    with pytest.raises(tc.TarecoError, match="cannot read 'soon'"):
        parse(["2026-01-01", "soon"], None)


def test_auto_frequency():
    auto = tl_module._auto_freq
    start = dt.datetime(2026, 1, 1)
    assert auto(start, start + dt.timedelta(days=10)) == "day"
    assert auto(start, start + dt.timedelta(days=90)) == "week"
    assert auto(start, start + dt.timedelta(days=360)) == "month"
    assert auto(start, start + dt.timedelta(days=5 * 365)) == "quarter"
    assert auto(start, start + dt.timedelta(days=20 * 365)) == "year"


def test_numeric_times():
    steps = tc.timeline([("a", "b", 1), ("b", "c", 2), ("c", "a", 2)], time=2)
    assert steps.periods == ["1", "2"] and steps["2"].edge_count == 2
    years = tc.timeline([("a", "b", 1990 + i) for i in range(60)], time=2, freq=10)
    assert years.periods == ["1990", "2000", "2010", "2020", "2030", "2040"]
    with pytest.raises(tc.TarecoError):
        tc.timeline([("a", "b", 1)], time=2, freq="month")


# ------------------------------------------------------------------ snapshots

def test_snapshots_union_and_activity():
    rows = [("a", "b", "2026-01-03", 5), ("b", "a", "2026-01-20", 1), ("b", "c", "2026-03-02", 2)]
    t = tc.timeline([{"s": a, "t": b, "d": d, "v": v} for a, b, d, v in rows], time="d", weight="v",
                    freq="month")
    assert t.periods == ["2026-01", "2026-02", "2026-03"] and t.freq == "month"
    jan = t["2026-01"]
    assert jan.edge_count == 1 and jan.edges["a", "b"] == {"weight": 6, "count": 2}
    assert t[1].edge_count == 0  # quiet months stay in the timeline
    assert t.union.edges["b", "c"] == {"weight": 2, "count": 1, "first": "2026-03", "last": "2026-03", "periods": [2]}
    assert t.union.edges["a", "b"]["periods"] == [0]
    assert [a["connections"] for a in t.activity()] == [1, 0, 1]
    assert repr(t) == "<Timeline by month, 3 periods, 3 nodes, 2 connections>"
    with pytest.raises(tc.TarecoError, match="no period"):
        t["2027-01"]
    growing = tc.timeline([{"s": a, "t": b, "d": d} for a, b, d, _ in rows], time="d", cumulative=True,
                          freq="month")
    assert [g.edge_count for _, g in growing] == [1, 1, 2]
    assert [a["connections"] for a in growing.activity()] == [1, 0, 1]


def test_weight_is_picked_like_in_a_graph():
    rows = [{"sender": "a", "receiver": "b", "when": "2026-01-05", "amount": 10},
            {"sender": "a", "receiver": "b", "when": "2026-01-09", "amount": 5},
            {"sender": "b", "receiver": "c", "when": "2026-02-01", "amount": 1}]
    assert tc.timeline(rows, time="when").union.edges["a", "b"]["weight"] == 15
    events = [{k: v for k, v in r.items() if k != "amount"} for r in rows]
    assert tc.timeline(events, time="when").union.edges["a", "b"]["weight"] == 2  # no number: count events
    with pytest.raises(tc.TarecoError, match="no column 'kg'"):
        tc.timeline(rows, time="when", weight="kg")
    with pytest.raises(tc.TarecoError, match="cannot be the weight"):
        tc.timeline(rows, time="when", weight="when")


def test_columns_and_errors():
    with pytest.raises(tc.TarecoError, match="no column 'when'"):
        tc.timeline([{"a": 1, "b": 2, "t": 3}], time="when")
    with pytest.raises(tc.TarecoError, match="no rows"):
        tc.timeline([{"a": 1, "b": None, "t": 3}], time="t")
    t = tc.timeline([{"x": "a", "y": "b", "t": 1}], time="t", source="y", target="x", directed=True)
    assert t.union.has_edge("b", "a")


# -------------------------------------------------------------------- changes

def test_changes_tell_the_story():
    t = story()
    text = [f.text for f in t.changes()]
    assert "30 new nodes showed up in 2026-04." in text
    assert "star appeared in 2026-05 with 25 connections at once." in text
    newcomers = next(f for f in t.changes() if f.kind == "newcomers")
    assert newcomers.period == 3 and len(newcomers.nodes) == 30
    pt = [f.text for f in t.changes(lang="pt")]
    assert "30 nós novos apareceram em 2026-04." in pt


def classes(party=None, seed=3):
    """Three weeks of eight classes meeting in random pairs every day, plus a few chance
    meetings across classes; maybe a party on day 10."""
    rng = random.Random(seed)
    people = [f"P{i:03d}" for i in range(160)]
    rows = []
    for d in range(1, 22):
        for c in range(8):
            for _ in range(6):
                a, b = rng.sample(people[c * 20:(c + 1) * 20], 2)
                rows.append((a, b, f"2026-05-{d:02d}"))
        for _ in range(4):
            a, b = rng.sample(people, 2)
            rows.append((a, b, f"2026-05-{d:02d}"))
        if d == 10 and party:
            rows += [(party, p, "2026-05-10") for p in rng.sample(people, 40) if p != party]
    return tc.timeline(rows, time=2, freq="day")


@pytest.mark.parametrize("seed", [3, 4, 5, 6])
def test_a_network_filling_up_is_not_news(seed):
    quiet = classes(seed=seed)
    kinds = {f.kind for f in quiet.changes()}
    assert "newcomers" not in kinds and "new_group" not in kinds
    party = [f for f in classes(party="P077", seed=seed).changes() if f.kind == "new_group"]
    assert len(party) == 1 and "P077" in party[0].nodes and len(party[0].nodes) >= 20


def test_activity_and_groups_changes():
    rows = []
    for i in range(10):
        rows += [(f"a{i}", f"a{(i + 1) % 10}", "2026-01-05"), (f"b{i}", f"b{(i + 1) % 10}", "2026-01-05")]
    everyone = [f"a{i}" for i in range(10)] + [f"b{i}" for i in range(10)]
    rows += [(x, y, "2026-02-05") for k, x in enumerate(everyone) for y in everyone[k + 1:]]
    t = tc.timeline(rows, time=2, freq="month")
    kinds = {f.kind for f in t.changes()}
    assert "activity_up" in kinds and "merge" in kinds


def test_explain_over_time():
    e = story().explain()
    text = str(e)
    assert text.splitlines()[1] == "- From 2026-01 to 2026-06 (6 months): 61 nodes and 467 connections in total."
    assert "The busiest period was 2026-05" in text
    assert "The most important nodes are" in text
    quiet = tc.timeline([("a", "b", "2026-01-01"), ("a", "b", "2026-04-01")], time=2, freq="month")
    assert "Nothing happened in 2 of the periods." in str(quiet.explain())


def test_spread_respects_the_order_of_events():
    rows = [("a", "b", 1), ("c", "d", 2), ("b", "c", 3), ("d", "e", 4)]
    t = tc.timeline(rows, time=2, directed=True)
    assert t.spread("a") == {"a": 1, "b": 1, "c": 3, "e": 4} or t.spread("a") == {"a": 1, "b": 1, "c": 3}
    reached = t.spread("a")
    assert "d" not in reached  # c met d before c heard from b
    assert list(t.spread("c")) == ["c", "d", "e"]
    undirected = tc.timeline(rows, time=2)
    assert set(undirected.spread("e")) == {"e", "d"}
    assert t.spread("a", since=3) == {"a": 3}
    with pytest.raises(tc.TarecoError):
        t.spread("zz")


# ----------------------------------------------------------------------- view

def payload(page):
    return json.loads(re.search(r"window\.__TARECO__ = (.*?);</script>", page, re.S).group(1))


def test_timeline_view_carries_periods():
    t = story(directed=True)
    page = t.to_html(lang="pt")
    assert all(ord(c) < 128 for c in page) and "tarecoTimebar" in page
    p = payload(page)
    assert p["config"]["time"]["periods"][0] == "2026-01" and len(p["config"]["time"]["counts"]) == 6
    assert all(link["p"] for link in p["links"]) and "periods" not in p["links"][0]["attrs"]
    first = p["config"]["insights"][0]
    assert first["kind"] == "time_span" and first["text"].startswith("De 2026-01 a 2026-06")
    assert any(f["period"] == 3 for f in p["config"]["insights"])
    webgl = payload(t.to_html(renderer="webgl"))
    assert len(webgl["edges"]["p"]) == len(webgl["edges"]["e"]) // 2
    assert t._repr_html_().startswith('<div class="tareco-graph">')


def test_timeline_show(monkeypatch):
    opened = []
    monkeypatch.setattr("webbrowser.open", lambda url: opened.append(url) or True)
    story().show(title="x")
    assert len(opened) == 1

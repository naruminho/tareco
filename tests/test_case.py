import datetime as dt
import gzip
import json
from decimal import Decimal

import pytest

import tareco as tc
from tareco.io import GuessWarning

ROWS = [{"tid": f"T{k}", "from": "p", "to": f"q{k % 2}", "amount": 9500 + k,
         "date": dt.datetime(2026, 1, k + 1, 9, 30)} for k in range(6)]
ROWS += [{"tid": f"S{k}", "from": f"c{k}", "to": f"shop{k % 3}", "amount": 20 + k, "date": dt.date(2026, 1, 2)}
         for k in range(30)]


def investigation():
    g = tc.Graph(ROWS, directed=True, kind="transfer", keep=True, source_kind="account", target_kind="account")
    with pytest.warns(GuessWarning):
        g.add_links([{"account": "p", "device": "q0"}, {"account": "c1", "device": "d9"}],
                    source="account", target="device", kind="uses")
    g.add_node("p", opened=dt.date(2020, 5, 1), limit=Decimal("10000.50"), tags={"vip"}, pair=(1, "x"))
    g.add_edge("c1", "c2", amount=7.5, kind="transfer")
    return g


def test_a_saved_investigation_comes_back_whole(tmp_path):
    g = investigation()
    path = g.save(tmp_path / "case.tareco")
    h = tc.load(path)
    assert h.directed and len(h) == len(g) and h.edge_count == g.edge_count
    assert h.attrs == g.attrs and h.attrs["prefixes"] == {"device": "device:"}
    assert dict(h.nodes.items()) == dict(g.nodes.items())
    assert {e: d for e, d in h.edges.items()} == {e: d for e, d in g.edges.items()}
    assert h._events == g._events
    p = h.nodes["p"]
    assert p["opened"] == dt.date(2020, 5, 1) and p["limit"] == Decimal("10000.50")
    assert p["tags"] == {"vip"} and p["pair"] == (1, "x")
    assert h.rows("p")[0]["date"] == dt.datetime(2026, 1, 1, 9, 30)
    assert [r.node for r in h.review(lang="en")] == [r.node for r in g.review(lang="en")]
    assert repr(h.explain(lang="en")) == repr(g.explain(lang="en"))


def test_odd_ids_and_keys_survive(tmp_path):
    g = tc.Graph([((1, "a"), 2, {"w": 1}), (2, "x", {"$": "dollar", 3: "three"})], directed=False)
    g.attrs["link_kinds"] = {None: {"directed": False}}
    h = tc.load(g.save(tmp_path / "odd.tareco"))
    assert set(h) == {(1, "a"), 2, "x"} and not h.directed
    assert h.edges[2, "x"] == {"$": "dollar", 3: "three"}
    assert h.attrs["link_kinds"] == {None: {"directed": False}}


def test_a_case_file_opens_wherever_a_table_does(tmp_path):
    path = investigation().save(tmp_path / "case.tareco")
    assert tc.Graph(path).edge_count == investigation().edge_count
    assert "just under 10,000" in repr(tc.explain(path, lang="en"))
    with gzip.open(path, "rt", encoding="utf-8") as f:
        data = json.load(f)
    assert data["format"] == "tareco" and data["version"] == 1 and data["tareco"] == tc.__version__


def test_files_that_are_not_cases_say_so(tmp_path):
    plain = tmp_path / "plain.tareco"
    plain.write_text("from,to\na,b\n")
    with pytest.raises(tc.TarecoError, match="not a file saved by tareco"):
        tc.load(plain)
    newer = tmp_path / "newer.tareco"
    with gzip.open(newer, "wt", encoding="utf-8") as f:
        json.dump({"format": "tareco", "version": 99, "tareco": "9.0.0"}, f)
    with pytest.raises(tc.TarecoError, match="upgrade"):
        tc.load(newer)
    with pytest.raises(tc.TarecoError, match="file not found"):
        tc.load(tmp_path / "missing.tareco")
    with pytest.raises(tc.TarecoError, match="whole graph"):
        investigation().save(tmp_path / "x.tareco", color="pagerank")

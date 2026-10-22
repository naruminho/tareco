"""Bank statements, several kinds of link, and the way back from a finding to the rows behind it."""

import warnings

import pytest

import tareco as tc
from tareco.io import GuessWarning

# a1 and a2 are customers: their transfer shows on both statements; BOSS and SHOP are outside
STATEMENT = [
    {"tid": "T1", "account": "a1", "counterparty": "a2", "amount": -100.0, "date": "2026-01-02"},
    {"tid": "T2", "account": "a2", "counterparty": "a1", "amount": 100.0, "date": "2026-01-02"},
    {"tid": "T3", "account": "a2", "counterparty": "SHOP", "amount": -40.0, "date": "2026-01-03"},
    {"tid": "T4", "account": "a1", "counterparty": "BOSS", "amount": 3000.0, "date": "2026-01-05"},
    {"tid": "T5", "account": "a1", "counterparty": "a2", "amount": -50.0, "date": "2026-01-06"},
    {"tid": "T6", "account": "a2", "counterparty": "a1", "amount": 50.0, "date": "2026-01-06"},
]


def statement(**options):
    return tc.Graph(STATEMENT, account="account", counterparty="counterparty", **options)


# ------------------------------------------------------------------- statements

def test_the_sign_gives_the_direction_and_each_transfer_counts_once():
    g = statement()
    assert g.directed and g.attrs["weight"] == "amount"
    assert set(g.edges) == {("a1", "a2"), ("a2", "SHOP"), ("BOSS", "a1")}
    assert g.edges["a1", "a2"]["amount"] == 150.0 and g.edges["a1", "a2"]["count"] == 2
    assert g.edges["BOSS", "a1"]["amount"] == 3000.0  # money in from outside
    assert g.nodes["a1"]["kind"] == "account" and g.nodes["SHOP"]["kind"] == "counterparty"
    assert g.edges["a1", "a2"]["tid"] == "T1"  # text and ids keep the first value, amounts add up


def test_statement_errors():
    with pytest.raises(tc.TarecoError, match="both account= and counterparty="):
        tc.Graph(STATEMENT, account="account")
    with pytest.raises(tc.TarecoError, match="no column 'acct'"):
        tc.Graph(STATEMENT, account="acct", counterparty="counterparty")
    rows = [{"account": "a", "counterparty": "b", "x": -1, "y": -2}]
    with pytest.raises(tc.TarecoError, match="which column has the amount"):
        tc.Graph(rows, account="account", counterparty="counterparty")
    assert tc.Graph(rows, account="account", counterparty="counterparty", amount="y").edges["a", "b"]["y"] == 2


def test_statement_timeline():
    t = tc.timeline(STATEMENT, time="date", account="account", counterparty="counterparty", freq="day")
    assert t.directed
    assert t.union.edges["a1", "a2"]["weight"] == 150.0 and t.union.edges["a1", "a2"]["count"] == 2


# ------------------------------------------------------------------------ kinds

def test_links_of_another_kind():
    g = statement(kind="transfer")
    logins = [{"account": "a1", "device": "d1"}, {"account": "a2", "device": "d1"},
              {"account": "a2", "device": "d2"}]
    assert g.add_links(logins, source="account", target="device", kind="uses") is g
    assert g.kinds() == {"links": {"transfer": 3, "uses": 3},
                         "nodes": {"account": 2, "counterparty": 2, "device": 2}}
    assert g.attrs["link_kinds"] == {"transfer": {"directed": True}, "uses": {"directed": False}}
    assert g.edges["a1", "d1"] == {"kind": "uses"}
    only = g.only("transfer")
    assert "d1" not in only and only.kinds()["links"] == {"transfer": 3}
    shared = g.project("account", via="device")
    assert list(shared.edges) == [("a1", "a2")] and shared.edges["a1", "a2"]["examples"] == "d1"
    with pytest.raises(tc.TarecoError, match="no nodes of kind 'person'"):
        g.project("person")


def test_two_kinds_between_one_pair_share_the_edge():
    g = tc.Graph([{"from": "a", "to": "b", "amount": 5}], kind="transfer", directed=True)
    g.add_links([{"from": "a", "to": "b"}], kind="family", directed=True)
    assert g.edge_count == 1 and g.edges["a", "b"]["kind"] == ("family", "transfer")
    assert g.kinds()["links"] == {"family": 1, "transfer": 1}
    assert g.only("family").edge_count == 1


def test_node_kinds_from_column_names():
    g = tc.Graph()
    g.add_links([{"person_a": "x", "person_b": "y"}], source="person_a", target="person_b", kind="knows")
    assert g.nodes["x"]["kind"] == "person"  # one kind, two roles
    h = tc.Graph()
    h.add_links([{"payer": "x", "payee": "y"}], source="payer", target="payee", kind="pays")
    assert "kind" not in h.nodes["x"]  # payer and payee are roles, not kinds of thing


def test_clashing_ids_get_a_prefix():
    g = statement(kind="transfer")
    with pytest.warns(GuessWarning, match="device:a2"):
        g.add_links([{"account": "a1", "device": "a2"}], source="account", target="device", kind="uses")
    assert ("a1", "device:a2") in g.edges and g.attrs["prefixes"] == {"device": "device:"}
    g.add_links([{"account": "a2", "device": "zz"}], source="account", target="device", kind="uses")
    assert ("a2", "device:zz") in g.edges  # the same kind keeps its prefix


def test_direction_rules():
    g = tc.Graph([("a", "b")])
    with pytest.raises(tc.TarecoError, match="already has links without direction"):
        g.add_links([{"from": "b", "to": "c"}], directed=True)
    empty = tc.Graph(nodes=[{"id": "a", "city": "x"}])
    empty.add_links([{"from": "a", "to": "b"}], directed=True)
    assert empty.directed and empty.nodes["a"] == {"city": "x"}
    with pytest.raises(tc.TarecoError, match="work with tables"):
        tc.Graph([("a", "b")], kind="x")


# ------------------------------------------------------------------- kept rows

def test_rows_behind_the_links():
    g = statement(keep=True)
    assert [r["tid"] for r in g.rows("SHOP")] == ["T3"]
    assert [r["tid"] for r in g.rows(link=("a1", "a2"))] == ["T1", "T5"]
    assert len(g.rows(["a1", "a2"])) == 4
    assert g.rows("SHOP").column("amount") == [-40.0]  # as it was in the table
    assert len(g.copy().rows()) == 4 and len(g.subgraph(["a1", "a2"]).rows()) == 2
    g.remove_edge("a1", "a2")
    assert len(g.rows()) == 2
    with pytest.raises(tc.TarecoError, match="keep=True"):
        statement().rows("a1")
    picked = tc.Graph(STATEMENT, account="account", counterparty="counterparty", keep=["tid"])
    assert picked.rows("SHOP") == [{"tid": "T3"}]
    with pytest.raises(tc.TarecoError, match="no column 'nope' to keep"):
        tc.Graph(STATEMENT, account="account", counterparty="counterparty", keep=["nope"])


def test_records_finds_rows_in_your_own_table(tmp_path):
    rows = tc.records(STATEMENT, ["SHOP", "BOSS"], columns="counterparty")
    assert [r["tid"] for r in rows] == ["T3", "T4"]
    edges = [{"from": "a", "to": "b", "n": 1}, {"from": "c", "to": "d", "n": 2}]
    assert tc.records(edges, "d") == [{"from": "c", "to": "d", "n": 2}]  # source and target by default
    pd = pytest.importorskip("pandas")
    df = pd.DataFrame(STATEMENT)
    found = tc.records(df, "a1", columns=["account"])
    assert list(found["tid"]) == ["T1", "T4", "T5"]
    with pytest.raises(tc.TarecoError, match="no column 'x'"):
        tc.records(df, "a1", columns=["x"])

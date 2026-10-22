"""Behaviors worth a look: amounts far above the usual, piles under a limit, misfits, closeness, flows."""

import datetime as dt
import random
from pathlib import Path

import pytest

import tareco as tc
from tareco.indicators import _round_above, parse_span

STATEMENTS = Path(__file__).resolve().parent.parent / "examples" / "recipes" / "09-statements"


def day(n):
    return (dt.date(2026, 1, 1) + dt.timedelta(days=n)).isoformat()


def payments(seed=1):
    """Thirty people paying shops and each other small amounts every few days."""
    rng = random.Random(seed)
    people = [f"p{i:02d}" for i in range(30)]
    rows = []
    for d in range(0, 120, 3):
        for p in people:
            rows.append({"id": f"r{len(rows)}", "from": p, "to": rng.choice(["shopA", "shopB", "shopC"]),
                         "amount": round(rng.uniform(10, 300), 2), "date": day(d)})
    return people, rows


@pytest.fixture(scope="module")
def bank():
    g = tc.Graph(STATEMENTS / "statements.csv", account="account", counterparty="counterparty",
                 kind="transfer", nodes=STATEMENTS / "customers.csv", keep=True)
    g.add_links(STATEMENTS / "logins.csv", source="account", target="device", kind="uses")
    return g


# ------------------------------------------------------------------- amounts

def test_unusual_amounts():
    _, rows = payments()
    rows.append({"id": "big", "from": "p07", "to": "shopB", "amount": 25000, "date": day(50)})
    g = tc.Graph(rows, directed=True, keep=True)
    found = g.unusual_amounts(lang="en")
    assert len(found) == 1 and found[0].nodes == ["p07", "shopB"]
    assert "p07 sent 25,000 to shopB on 2026-02-20" in found[0].text
    assert found[0].rows.column("id") == ["big"]
    with pytest.raises(tc.TarecoError, match="keep=True"):
        tc.Graph(rows, directed=True).unusual_amounts()


def test_round_limits_and_spans():
    assert _round_above(9700, 0.1) == 10000 and _round_above(4850, 0.1) == 5000
    assert _round_above(2950, 0.1) == 3000 and _round_above(1234, 0.1) is None
    assert parse_span("7 days") == dt.timedelta(days=7) and parse_span("48 hours") == dt.timedelta(hours=48)
    assert parse_span(3) == dt.timedelta(days=3) and parse_span("2w") == dt.timedelta(weeks=2)
    with pytest.raises(tc.TarecoError):
        parse_span("soon")


def test_splits_find_piles_under_a_limit():
    people, rows = payments()
    for k, amount in enumerate((9500, 9800, 9650, 9900, 9720, 9610)):
        rows.append({"id": f"s{k}", "from": "p03", "to": f"far{k % 3}", "amount": amount, "date": day(40 + k)})
    g = tc.Graph(rows, directed=True, keep=True)
    explicit = g.splits(limit=10_000, lang="en")
    assert explicit[0].nodes[0] == "p03" and explicit[0].details["count"] == 6
    assert "p03 sent 6 transfers just under 10,000 within 5 days" in explicit[0].text
    assert sorted(explicit[0].rows.column("id")) == [f"s{k}" for k in range(6)]
    auto = g.splits(lang="en")
    assert [p.nodes[0] for p in auto] == ["p03"]  # nobody else piles anything


def test_salaries_of_every_size_are_not_a_pile():
    rng = random.Random(4)
    rows = [{"from": "payroll", "to": f"e{i}", "amount": round(rng.uniform(2500, 9000), 2), "date": day(5)}
            for i in range(300)]
    g = tc.Graph(rows, directed=True, keep=True)
    assert not g.splits(limit=5000) and not g.splits()


def test_many_senders_into_one():
    _, rows = payments()
    for k in range(5):
        rows.append({"id": f"in{k}", "from": f"p{k:02d}", "to": "pot", "amount": 2900 + k * 10, "date": day(60 + k)})
    found = tc.Graph(rows, directed=True, keep=True).splits(limit=3000, lang="en")
    assert found[0].nodes[0] == "pot" and found[0].details["side"] == "in"
    assert "pot received 5 transfers just under 3,000 from 5 senders" in found[0].text


# -------------------------------------------------------------------- misfits

def test_misfits():
    rows, nodes = [], []
    for i in range(12):
        nodes.append({"id": f"r{i}", "income": 100_000 + i * 1000, "job": "executive"})
    nodes.append({"id": "cleaner", "income": 2000, "job": "cleaner"})
    for i in range(12):
        for j in range(i + 1, 12):
            if (i + j) % 3 == 0:
                rows.append((f"r{i}", f"r{j}"))
    rows += [("cleaner", f"r{i}") for i in range(6)]
    g = tc.Graph(rows, nodes=nodes)
    numbers = g.misfits("income", lang="en")
    assert numbers[0].nodes[0] == "cleaner" and "51x lower than the median of the 6 nodes" in numbers[0].text
    jobs = g.misfits("job", lang="en")
    assert jobs[0].nodes[0] == "cleaner" and "100% of the 6 nodes it deals with have executive" in jobs[0].text
    with pytest.raises(tc.TarecoError, match="not a node attribute"):
        g.misfits("nope")


# ----------------------------------------------------------------------- near

def test_near_skips_hubs_and_reports_the_same_kind(bank):
    found = bank.near(["a017"], lang="en")
    assert [p.nodes[0] for p in found] == ["a142", "a023", "a199"] or \
        sorted(p.nodes[0] for p in found) == ["a023", "a142", "a199"]
    assert all("through dev-77 (device)" in p.text for p in found)
    flagged = tc.Graph([("x", "hub")] + [(f"n{i}", "hub") for i in range(40)] + [("x", "y")])
    near = flagged.near("x", lang="en")
    assert [p.nodes[0] for p in near if p.details["steps"] == 2] == []  # nobody through the hub
    assert {p.nodes[0] for p in near} == {"hub", "y"}
    with pytest.raises(tc.TarecoError, match="neither a node"):
        flagged.near("zzz")


def test_flows_by_an_attribute(bank):
    flows = bank.flows(by="counterparty_country", lang="en")
    assert [f.value for f in flows] == ["Northland", "Westland", "Palm Isles"]
    assert set(flows["Palm Isles"].nodes) == {"a017", "a023", "a142", "a120"}
    assert "Palm Isles: " in repr(flows) and "and 1 more" in repr(flows)
    g = tc.Graph([("a", "b", 5), ("a", "c", 1)], directed=True, nodes=[{"id": "b", "land": "x"}])
    by_node = g.flows(by="land")
    assert by_node["x"].amount == 5 and by_node[None].amount == 1
    assert g.flows(by="land", direction="from")[0].value is None


# ------------------------------------------------------------- explain, why, similar

def test_explain_names_what_was_planted(bank):
    text = str(bank.explain(lang="en"))
    assert "Links: 7,303 transfer and 342 uses." in text
    assert "4 account nodes share dev-77 (device)." in text
    assert "a017 sent 8 transfers just under 10,000" in text
    assert "a055 sent 85,000 to ART-DEALER-W" in text
    assert "a023 has monthly_income 2,060, 67x lower" in text
    assert "SHOP-04 has" not in text and "receives from 171 nodes" not in text  # shops are not news


def test_why_tells_one_account(bank):
    text = str(bank.why("a023", watch=["a017"], lang="en"))
    assert text.startswith("About a023\n- a023 (account): occupation cleaner")
    assert "passes almost all of it on" in text and "467x what it usually sends" in text
    assert "It shares dev-77 (device) with" in text and "is 2 steps from a017" in text
    quiet = tc.Graph([("a", "b"), ("b", "c")])
    assert "Nothing stands out about a." in str(quiet.why("a", lang="en"))


def test_similar_to_finds_the_twin(bank):
    alike = bank.similar_to("a017", n=3, lang="en")
    assert alike.nodes[0] == "a142"
    assert "piles amounts just under a round limit" in alike[0].reasons
    assert all(bank.nodes[x]["kind"] == "account" for x in alike.nodes)
    assert repr(alike).startswith("Most like a017\n- a142 (")
    both = bank.similar_to(["a017", "a142"], n=2)
    assert "a017" not in both.nodes and "a142" not in both.nodes


def test_everything_reads_in_portuguese_too(bank):
    why = str(bank.why("a023", watch=["a017"], lang="pt"))
    assert why.startswith("Sobre a023") and "Compartilha dev-77 (device) com" in why
    assert "está a 2 passos de a017" in why
    assert "enviou 8 transferências logo abaixo de 10.000" in bank.splits(limit=10_000, lang="pt")[0].text
    assert repr(bank.flows(by="counterparty_country", lang="pt")).startswith("Para onde vai, por counterparty_country")
    assert repr(bank.similar_to("a017", n=1, lang="pt")).startswith("Mais parecidos com a017")
    assert "Ligações: 7.303 transfer e 342 uses." in str(bank.explain(lang="pt"))


def test_review_ranks_the_planted_cases(bank):
    review = bank.review(watch=["a017"], limit=10_000, lang="en")
    assert set(review.nodes[:3]) == {"a023", "a142", "a017"}
    first = review[0]
    assert first.node == "a023" and any("passes almost all of it on" in r for r in first.reasons)
    assert any(r.endswith("(and 4 more like it)") for r in first.reasons)
    a017 = review[review.nodes.index("a017")]
    assert a017.ids == ["T009037", "T009038", "T009125", "T009193", "T009281", "T009282", "T009346", "T009430"]
    assert review.id_column == "transaction_id"
    text = repr(review)
    assert text.startswith("Worth a look\n1. a023 (score ") and ", 5 rows behind it" in text
    table = review.table()
    assert table[0]["node"] == "a023" and "pass_through" in table[0]["signals"] and table[0]["occupation"] == "cleaner"
    pd = pytest.importorskip("pandas")
    frame = review.to_pandas()
    assert list(frame.columns[:6]) == ["node", "score", "signals", "reasons", "rows", "ids"]
    assert repr(bank.review(top=1, lang="pt")).startswith("Vale um olhar\n1. ")
    quiet = tc.Graph([("a", "b"), ("b", "c")])
    assert len(quiet.review()) == 0

"""What in a table would mislead the graph: placeholders, ids written two ways, copies, bad dates."""

import warnings

import pytest

import tareco as tc
from tareco.io import looks_like_placeholder

ROWS = [{"from": "a", "to": "b", "amount": 10, "date": "2026-01-02"},
        {"from": "a", "to": "b", "amount": 10, "date": "2026-01-02"},          # a copy
        {"from": "b", "to": "N/A", "amount": 5, "date": "2026-01-03"},
        {"from": "c", "to": "N/A", "amount": 0, "date": "yesterday"},          # zero, bad date
        {"from": "c", "to": "c", "amount": 3, "date": "2026-01-04"},           # itself
        {"from": 123, "to": "123", "amount": "ten", "date": "2026-01-05"},     # number and text
        {"from": "ACME ", "to": "acme", "amount": 2, "date": "2026-01-06"},
        {"from": "d", "to": None, "amount": 1, "date": "2026-01-07"}]


def test_placeholders():
    for value in ("N/A", "unknown", " NULL ", "0", "000", "99999", "XXX", "-", "?", 0, -1, 999999, ""):
        assert looks_like_placeholder(value), value
    for value in ("ana", "a017", 17, 1, "X1", "9", 99, True, None):
        assert not looks_like_placeholder(value), value


def test_check_lists_what_to_fix():
    found = tc.check(ROWS, lang="en")
    kinds = [i.kind for i in found]
    assert kinds == ["missing", "placeholder", "self", "duplicates", "mixed_types", "variants",
                     "amount_text", "amount_zero", "dates"]
    text = repr(found)
    assert text.startswith("9 things to look at in 8 rows")
    assert "Rows with a placeholder in to ('N/A'): 2." in text
    assert "Ids written both as a number and as text (123): 1." in text
    assert "'ACME ' / 'acme'" in text and "'yesterday'" in text
    assert repr(tc.check([{"from": "a", "to": "b"}], lang="en")) == "Nothing to fix in 1 row."
    statement = [{"account": "a", "counterparty": "b", "amount": 5}]
    assert "No amount in amount is negative" in repr(tc.check(statement, account="account",
                                                             counterparty="counterparty", lang="en"))
    assert "Linhas com um coringa em to ('N/A'): 2." in repr(tc.check(ROWS, lang="pt"))
    assert repr(tc.check(ROWS[:2], lang="en")).startswith("1 thing to look at in 2 rows")


def test_placeholders_warn_and_skip_leaves_them_out():
    rows = [{"from": f"p{i}", "to": "UNKNOWN", "amount": 1} for i in range(30)] + [{"from": "a", "to": "b"}]
    with pytest.warns(tc.DataWarning, match="'UNKNOWN' is the target of 30 rows"):
        g = tc.Graph(rows)
    assert "UNKNOWN" in g
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        clean = tc.Graph(rows, skip=["UNKNOWN"])
    assert "UNKNOWN" not in clean and clean.edge_count == 1
    few = [{"from": "a", "to": "0"}, {"from": "b", "to": "c"}]
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        tc.Graph(few)  # one "0" is just a node called 0
    st = [{"account": "a", "counterparty": "N/A", "amount": -5}, {"account": "a", "counterparty": "b", "amount": -1}]
    assert set(tc.Graph(st, account="account", counterparty="counterparty", skip="N/A")) == {"a", "b"}


def test_timeline_skips_too():
    rows = [{"from": "a", "to": "N/A", "when": "2026-01-01"}, {"from": "a", "to": "b", "when": "2026-01-02"}]
    assert set(tc.timeline(rows, time="when", skip=["N/A"]).union) == {"a", "b"}

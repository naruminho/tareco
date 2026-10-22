"""What changed between two work lists."""

import pytest

import tareco as tc

ROWS = [{"tid": f"T{k}", "from": "p", "to": f"q{k % 2}", "amount": 9500 + k, "date": f"2026-01-0{k + 1}"}
        for k in range(6)]
ROWS += [{"tid": f"S{k}", "from": f"c{k}", "to": f"shop{k % 3}", "amount": 20 + k, "date": "2026-01-02"}
         for k in range(30)]
LATER = [{"tid": "M1", "from": "c1", "to": "mule", "amount": 30000, "date": "2026-01-03"},
         {"tid": "M2", "from": "mule", "to": "far", "amount": 29000, "date": "2026-01-04"},
         {"tid": "P1", "from": "x", "to": "p", "amount": 30000, "date": "2026-01-02"},
         {"tid": "P2", "from": "p", "to": "far2", "amount": 28000, "date": "2026-01-03"}]


def lists():
    before = tc.Graph(ROWS, directed=True, keep=True).review(limit=10_000, lang="en")
    now = tc.Graph(ROWS + LATER, directed=True, keep=True).review(limit=10_000, lang="en")
    return before, now


def test_new_up_and_gone_since_the_last_review():
    before, now = lists()
    changes = now.compare(before)
    assert [r.node for r in changes.new] == ["mule"]
    (p, score, fresh), = changes.up
    assert p.node == "p" and score == before[0].score and p.score > score
    assert len(fresh) == 1 and fresh[0].startswith("p received 30,000 and passed on")
    assert changes.nodes == ["mule", "p"] and not changes.down and not changes.gone
    text = repr(changes)
    assert text.startswith("Since the last review\nNew in the list: 1\n- mule (score ")
    assert f"- p, score {score:g} before, {p.score:g} now\n   - p received 30,000" in text
    back = before.compare(now)
    assert [n for n, _ in back.gone] == ["mule"] and [r.node for r, _, _ in back.down] == ["p"]
    assert "No longer in the list: 1\n- mule (score " in repr(back)
    assert not now.compare(now) and repr(now.compare(now)) == "Nothing changed since the last review."


def test_an_earlier_review_can_come_back_as_a_table(tmp_path):
    before, now = lists()
    rows = before.table() + [{"node": "old", "score": 4.0, "signals": "split"}]
    changes = now.compare(rows)
    assert [r.node for r in changes.new] == ["mule"] and changes.gone == [("old", 4.0)]
    assert changes.up[0][2][0].startswith("p received")
    no_signals = now.compare([{"node": r["node"], "score": r["score"]} for r in rows])
    assert no_signals.up[0][2] == []  # without the signals column nothing counts as a new reason
    pd = pytest.importorskip("pandas")
    path = tmp_path / "last.csv"
    before.to_pandas().to_csv(path, index=False)
    assert now.compare(str(path)).nodes == ["mule", "p"]
    frame = changes.to_pandas()
    assert list(frame.columns) == ["node", "change", "score", "before", "reasons"]
    assert list(frame["change"]) == ["new", "up", "gone"]
    with pytest.raises(tc.TarecoError, match="'score'"):
        now.compare([{"node": "p"}])


def test_changes_in_portuguese():
    before = tc.Graph(ROWS, directed=True, keep=True).review(limit=10_000, lang="pt")
    now = tc.Graph(ROWS + LATER, directed=True, keep=True).review(limit=10_000, lang="pt")
    text = repr(now.compare(before))
    assert text.startswith("Desde a última triagem\nNovos na lista: 1\n") and "pontos antes" in text

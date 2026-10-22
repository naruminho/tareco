import pytest

import tareco as tc
from tareco.tuning import DEFAULTS

ROWS = [{"tid": f"T{k}", "from": "p", "to": f"q{k % 2}", "amount": 9500 + k, "date": f"2026-01-0{k + 1}"}
        for k in range(6)]
ROWS += [{"tid": f"S{k}", "from": f"c{k}", "to": f"shop{k % 3}", "amount": 20 + k, "date": "2026-01-02"}
         for k in range(30)]


@pytest.fixture(autouse=True)
def defaults():
    tc.settings(reset=True)
    yield
    tc.settings(reset=True)


def graph():
    return tc.Graph(ROWS, directed=True, keep=True)


def test_settings_change_what_the_tools_fall_back_on():
    g = graph()
    assert g.splits()
    with tc.settings(split_count=7):
        assert not g.splits()               # six amounts no longer make a pile
        assert g.splits(min_count=3)        # an argument still wins
    assert g.splits()                       # back as before the block
    tc.settings(split_count=7)
    assert not g.splits() and not [r for r in g.review() if r.node == "p"]
    tc.settings(reset=True)
    assert g.splits()


def test_a_limit_and_a_window_for_every_tool():
    g = graph()
    with tc.settings(split_limit=9_503):
        assert g.splits()[0].details["limit"] == 9_503   # three amounts sit just under it
    with tc.settings(split_limit=9_503, split_count=4):
        assert not g.splits()
    with tc.settings(split_within="2 days"):
        assert not g.splits()
    with tc.settings(misfit_factor=1, misfit_neighbors=1):
        assert tc.settings()["misfit_factor"] == 1


def test_weights_rank_the_work_list():
    g = graph()
    base = next(r.score for r in g.review() if r.node == "p")
    with tc.settings(weights={"split": DEFAULTS["weights"]["split"] + 7}):
        assert next(r.score for r in g.review() if r.node == "p") == pytest.approx(base + 7)
        assert tc.settings()["weights"]["fan_out"] == DEFAULTS["weights"]["fan_out"]  # the others stay


def test_settings_show_what_is_set():
    with tc.settings(unusual_factor=20):
        text = repr(tc.settings())
    assert "unusual_factor    20   (changed)" in text and "split_within      '7 days'" in text
    assert tc.settings()["unusual_factor"] == 10


def test_wrong_settings_say_why():
    with pytest.raises(tc.TarecoError, match="no setting 'split_limits'"):
        tc.settings(split_limits=10)
    with pytest.raises(tc.TarecoError, match="share between 0 and 1"):
        tc.settings(fast_share=80)
    with pytest.raises(tc.TarecoError, match="whole number"):
        tc.settings(fan_min=2.5)
    with pytest.raises(tc.TarecoError):
        tc.settings(fast_within="soon")
    with pytest.raises(tc.TarecoError, match="weights must be"):
        tc.settings(weights={"split": -1})
    assert tc.settings() == DEFAULTS        # nothing changed on the way

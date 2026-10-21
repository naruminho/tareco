"""The pages in a real browser: they draw, answer clicks and raise no JavaScript errors.

Pages are also opened the way Databricks shows ``displayHTML`` output: inside a
sandboxed iframe of its own, so tareco's iframe ends up nested in another one.
Needs ``pip install playwright`` and a Chromium-based browser (Playwright's own,
or the installed Chrome/Edge); skipped otherwise.
"""

import html
import os
import random

import pytest

import tareco as tc
from tareco.viz import notebook_html

sync_api = pytest.importorskip("playwright.sync_api")

HERE = os.path.dirname(os.path.abspath(__file__))
EXAMPLES = os.path.join(os.path.dirname(HERE), "examples")


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as p:
        launched = None
        for options in ({}, {"channel": "chrome"}, {"channel": "msedge"}):
            try:
                launched = p.chromium.launch(**options)
                break
            except Exception:
                continue
        if launched is None:
            pytest.skip("no Chromium-based browser available")
        yield launched
        launched.close()


class Page:
    """A page plus every JavaScript error it raised, in any frame."""

    def __init__(self, browser, markup, tmp_path, block_workers=False):
        path = tmp_path / f"page{random.randrange(10**9)}.html"
        path.write_text(markup, encoding="utf-8")
        self.context = browser.new_context(viewport={"width": 1280, "height": 800})
        self.page = self.context.new_page()
        self.errors = []
        self.page.on("pageerror", lambda e: self.errors.append(str(e)))
        self.page.on("console", lambda m: self.errors.append(m.text) if m.type == "error" else None)
        if block_workers:  # like a page whose security policy forbids workers
            self.page.add_init_script("window.Worker = function () { throw new Error('workers blocked'); };")
        self.page.goto(path.as_uri())
        self.app = self._app_frame()

    def _app_frame(self):
        for _ in range(100):
            for frame in self.page.frames:
                try:
                    if frame.query_selector("#graph"):
                        frame.wait_for_function("document.getElementById('counts').textContent.length > 0",
                                                timeout=15000)
                        return frame
                except Exception:
                    continue
            self.page.wait_for_timeout(100)
        raise AssertionError(f"tareco never started; errors: {self.errors}")

    def text(self, selector):
        return self.app.eval_on_selector(selector, "e => e.textContent")

    def visible(self, selector):
        return self.app.eval_on_selector(selector, "e => !e.hidden && getComputedStyle(e).display !== 'none'")

    def settle(self, ms=600):
        self.page.wait_for_timeout(ms)
        assert not self.errors, self.errors

    def close(self):
        self.context.close()


def databricks_like(cell_output):
    """displayHTML renders a cell's HTML inside a sandboxed iframe."""
    inner = html.escape(f"<!doctype html><html><body style='margin:0'>{cell_output}</body></html>", quote=True)
    return (f'<!doctype html><html><body style="margin:0"><iframe sandbox="allow-scripts" srcdoc="{inner}" '
            f'style="width:100%;height:700px;border:0"></iframe></body></html>')


def friends():
    return tc.Graph(os.path.join(EXAMPLES, "friends.csv"), nodes=os.path.join(EXAMPLES, "people.csv"))


def story():
    rng = random.Random(2)
    people = [f"p{i}" for i in range(60)]
    rows = []
    for month in range(1, 7):
        for _ in range(40 + month * 15):
            a, b = rng.sample(people[:30] if month < 4 else people, 2)
            rows.append((a, b, f"2026-{month:02d}-{rng.randint(1, 28):02d}"))
        if month == 5:
            rows += [(f"p{i}", "star", "2026-05-10") for i in range(25)]
    return tc.timeline(rows, time=2, directed=True)


def exercise(p):
    """Search, select, insights, path, legend and theme: the clicks people make first."""
    p.app.fill("#search", "Ana")
    p.app.press("#search", "Enter")
    p.settle()
    assert p.visible("#panel") and p.text("#panel-title").startswith("Ana")
    p.app.click("#btn-insights")
    p.settle()
    assert p.app.eval_on_selector_all(".finding", "els => els.length") > 3
    p.app.click("button.finding >> nth=1")
    p.settle()
    assert p.app.query_selector(".finding.on")
    p.app.click("#btn-path")
    for name in ("Ana", "Otto"):
        p.app.fill("#search", name)
        p.app.press("#search", "Enter")
        p.settle(300)
    assert "step" in p.text("#panel-title")
    p.app.click("#btn-path")
    if p.app.query_selector(".legend-item"):
        p.app.click(".legend-item >> nth=0")
        p.settle(300)  # the legend is drawn again, so look the item up again
        assert "off" in p.app.get_attribute(".legend-item >> nth=0", "class")
    before = p.app.evaluate("document.documentElement.dataset.theme")
    p.app.click("#btn-theme")
    p.settle(300)
    assert p.app.evaluate("document.documentElement.dataset.theme") != before


# ------------------------------------------------------------------ tests

@pytest.mark.parametrize("wrap", ["page", "databricks"])
def test_canvas_view(browser, tmp_path, wrap):
    g = friends()
    markup = g.to_html(title="Friends") if wrap == "page" else databricks_like(notebook_html(g, title="Friends"))
    p = Page(browser, markup, tmp_path)
    try:
        assert p.text("#counts") == "16 nodes · 31 edges"
        assert p.app.eval_on_selector_all("#graph canvas", "els => els.length") >= 1
        p.settle(1500)
        exercise(p)
    finally:
        p.close()


@pytest.mark.parametrize("wrap", ["page", "databricks"])
def test_webgl_view(browser, tmp_path, wrap):
    g = tc.Graph(os.path.join(EXAMPLES, "friends.csv"), nodes=os.path.join(EXAMPLES, "people.csv"))
    big = tc.scale_free_graph(4000, 3, seed=1)
    big.add_edges((f"{a}", f"{b}") for a, b in list(g.edges))  # friends inside a big graph
    markup = big.to_html() if wrap == "page" else databricks_like(notebook_html(big))
    p = Page(browser, markup, tmp_path)
    try:
        assert "4,016 nodes" in p.text("#counts")
        p.app.wait_for_function("document.body.dataset.layout !== undefined", timeout=15000)
        where = p.app.evaluate("document.body.dataset.layout")
        assert where in ("worker", "main-thread")
        if wrap == "page":
            assert where == "worker"
        p.settle(1500)
        exercise(p)
        p.app.click("#btn-groups")
        p.settle()
        assert "groups" in p.text("#counts")
        p.app.click("#btn-groups")
        p.settle()
    finally:
        p.close()


def test_layout_falls_back_when_workers_are_blocked(browser, tmp_path):
    p = Page(browser, tc.scale_free_graph(3000, 2, seed=4).to_html(), tmp_path, block_workers=True)
    try:
        p.app.wait_for_function("document.body.dataset.layout === 'main-thread'", timeout=15000)
        p.settle(1500)
    finally:
        p.close()


@pytest.mark.parametrize("renderer", ["canvas", "webgl"])
def test_timeline_view(browser, tmp_path, renderer):
    t = story()
    p = Page(browser, databricks_like(notebook_html(t.union, time=t._time_info(), insights=t.explain(lang="pt"),
                                                    renderer=renderer, lang="pt")), tmp_path)
    try:
        assert p.visible("#timebar") and p.text("#time-label") == "Todos os períodos"
        p.app.eval_on_selector("#time-range", "r => { r.value = '1'; r.dispatchEvent(new Event('input')); }")
        p.settle()
        assert p.text("#time-label").startswith("2026-02")
        p.app.click("#time-play")
        p.page.wait_for_timeout(1400)
        assert not p.text("#time-label").startswith("2026-02")
        p.app.click("#btn-insights")
        dated = p.app.query_selector("button.finding-newcomers")
        dated.click()
        p.settle()
        assert p.text("#time-label").startswith("2026-04")
    finally:
        p.close()


def test_report_page(browser, tmp_path):
    p = Page(browser, friends().report(title="Friends"), tmp_path)
    try:
        assert p.page.eval_on_selector_all("h2", "els => els.length") >= 4
        p.settle(1000)
    finally:
        p.close()

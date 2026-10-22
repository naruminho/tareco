"""The documentation site builds, and its links point at pages, not at markdown files."""

import importlib.util
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def test_site_builds(tmp_path):
    pytest.importorskip("markdown")
    spec = importlib.util.spec_from_file_location("build", ROOT / "docs" / "site" / "build.py")
    build = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build)
    out = tmp_path / "site"
    build.build(out)
    assert (out / "index.html").exists() and (out / "guide.html").exists() and (out / "style.css").exists()
    pages = sorted((out / "recipes").glob("*.html"))
    assert len(pages) == len(build.RECIPES) == 9
    statements = (out / "recipes" / "09-statements.html").read_text(encoding="utf-8")
    assert '<iframe src="09-statements/statements.html"' in statements
    assert (out / "recipes" / "09-statements" / "statements.svg").exists()
    for page in [out / "index.html", out / "guide.html", out / "recipes.html", *pages]:
        text = page.read_text(encoding="utf-8")
        local = [h for h in re.findall(r'href="([^"]+)"', text) if not h.startswith(("http", "#", "mailto:"))]
        assert not [h for h in local if ".md" in h], (page.name, local)
        for href in local:
            assert (page.parent / href.split("#")[0]).exists(), (page.name, href)

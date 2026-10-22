"""Build the documentation site: the README, the guide and every recipe with its live graphs.

    pip install markdown
    python docs/site/build.py site        # then open site/index.html

The recipes run first, so each recipe page embeds the interactive pages and the
pictures it makes. GitHub Actions publishes the result to GitHub Pages.
"""

import html
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parents[2]
REPO = "https://github.com/naruminho/tareco"
RECIPES = sorted(p for p in (ROOT / "examples" / "recipes").iterdir() if p.is_dir() and p.name[0].isdigit())


def run_recipes():
    env = dict(os.environ, TARECO_LANG="en", PYTHONPATH=str(ROOT), PYTHONIOENCODING="utf-8")
    for folder in RECIPES:
        script = next(folder.glob("*.py"))
        done = subprocess.run([sys.executable, str(script)], cwd=ROOT, env=env, capture_output=True)
        if done.returncode:
            raise SystemExit(f"{script} failed:\n{done.stderr.decode('utf-8', 'replace')}")


def target_of(path):
    """Where a file of the repository lives on the site, or None to send it to GitHub."""
    rel = path.relative_to(ROOT).as_posix().rstrip("/")
    if rel == "README.md":
        return "index.html"
    if rel == "docs/guide.md":
        return "guide.html"
    if rel == "examples/README.md":
        return "recipes.html"
    m = re.match(r"examples/recipes/(\d\d-[\w-]+)(/README\.md)?$", rel)
    if m:
        return f"recipes/{m.group(1)}.html"
    return None


def rewrite_links(body, source, page):
    """Links between the markdown files become links between pages; the rest goes to GitHub."""
    def fix(m):
        href = m.group(2)
        if href.startswith(("http://", "https://", "#", "mailto:")):
            return m.group(0)
        link, _, anchor = href.partition("#")
        path = (source.parent / link).resolve()
        if not str(path).startswith(str(ROOT)):
            return m.group(0)
        target = target_of(path)
        if target is None:
            rel = path.relative_to(ROOT).as_posix()
            new = f"{REPO}/{'tree' if path.is_dir() else 'blob'}/master/{rel}"
        else:
            new = os.path.relpath(target, os.path.dirname(page) or ".").replace(os.sep, "/")
        return f'{m.group(1)}"{new}{"#" + anchor if anchor else ""}"'
    return re.sub(r'(href=)"([^"]+)"', fix, body)


def page(title, body, depth, active):
    up = "../" * depth
    nav = "".join(f'<a href="{up}{href}"{" class=on" if name == active else ""}>{name}</a>'
                  for name, href in (("Home", "index.html"), ("Guide", "guide.html"), ("Recipes", "recipes.html")))
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)} - tareco</title><link rel="stylesheet" href="{up}style.css"></head>
<body><header><a class="brand" href="{up}index.html">tareco</a><nav>{nav}
<a href="{REPO}">GitHub</a><a href="https://pypi.org/project/tareco/">PyPI</a></nav></header>
<main>{body}</main>
<footer>tareco is free software. <a href="{REPO}">Source on GitHub</a>.</footer></body></html>"""


def render(path):
    text = path.read_text(encoding="utf-8")
    return markdown.markdown(text, extensions=["tables", "fenced_code", "toc"])


def title_of(path):
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem


def live(folder, out_dir):
    """The pages and pictures a recipe made, copied next to its page and embedded."""
    made = sorted((folder / "out").glob("*.html")) + sorted((folder / "out").glob("*.svg"))
    if not made:
        return ""
    target = out_dir / "recipes" / folder.name
    target.mkdir(parents=True, exist_ok=True)
    for f in made:
        shutil.copy(f, target / f.name)
    pages = [f for f in made if f.suffix == ".html"]
    parts = ['<section class="live"><h2>Try it</h2>']
    if pages:
        first = pages[0].name
        parts.append(f'<iframe src="{folder.name}/{first}" title="{html.escape(first)}" loading="lazy"></iframe>')
    links = " ".join(f'<a href="{folder.name}/{f.name}">{html.escape(f.name)}</a>' for f in made)
    parts.append(f'<p class="files">Open: {links}</p></section>')
    return "".join(parts)


def build(out_dir):
    out_dir = Path(out_dir)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    (out_dir / "recipes").mkdir(parents=True)
    shutil.copy(Path(__file__).with_name("style.css"), out_dir / "style.css")
    run_recipes()
    for source, name, active in ((ROOT / "README.md", "index.html", "Home"),
                                 (ROOT / "docs" / "guide.md", "guide.html", "Guide"),
                                 (ROOT / "examples" / "README.md", "recipes.html", "Recipes")):
        body = rewrite_links(render(source), source, name)
        (out_dir / name).write_text(page(title_of(source), body, 0, active), encoding="utf-8")
    for folder in RECIPES:
        source = folder / "README.md"
        name = f"recipes/{folder.name}.html"
        body = rewrite_links(render(source), source, name)
        first_h1 = body.find("</h1>")
        body = body[:first_h1 + 5] + live(folder, out_dir) + body[first_h1 + 5:] if first_h1 >= 0 else body
        (out_dir / name).write_text(page(title_of(source), body, 1, "Recipes"), encoding="utf-8")
    print(f"site written to {out_dir}")


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "site")

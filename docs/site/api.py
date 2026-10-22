"""The API reference page, written from the docstrings, so it never drifts from the code."""

import html
import inspect
import re
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tareco  # noqa: E402
from tareco import big  # noqa: E402
from tareco.entities import Entities  # noqa: E402
from tareco.indicators import Flows  # noqa: E402
from tareco.insights import Explanation  # noqa: E402
from tareco.patterns import Pattern, Patterns  # noqa: E402
from tareco.quality import Check  # noqa: E402
from tareco.review import Changes, Review  # noqa: E402
from tareco.tracing import Rows  # noqa: E402

START = ["show", "save", "explain", "report", "check", "load", "records", "compare", "timeline", "neighborhood",
         "project", "settings", "set_language", "doctor", "read_csv", "read_json", "read_excel"]
RESULTS = [Explanation, Patterns, Pattern, Review, Changes, Check, Rows, Entities, Flows, tareco.Timeline]
SPARK = ["statement_edges", "degrees", "components", "pagerank", "communities"]
PARAM = re.compile(r"^(\S+(?:, \S+)*)\s{2,}(\S.*)$")


def inline(text):
    """Escaped text with ``code`` marked up."""
    return re.sub(r"``(.+?)``", r"<code>\1</code>", html.escape(text, quote=False))


def definitions(lines):
    """``name   what it is`` lines (and names alone with the text indented below) as a list, or None."""
    items = []
    for line in lines:
        m = PARAM.match(line)
        if not line.startswith(" ") and m:
            items.append([m.group(1), m.group(2)])
        elif not line.startswith(" "):
            items.append([line.strip(), ""])
        elif items:
            items[-1][1] = (items[-1][1] + " " + line.strip()).strip()
        else:
            return None
    if not items or any(not text for _, text in items):
        return None
    return "<dl>" + "".join(f"<dt><code>{html.escape(name)}</code></dt><dd>{inline(text)}</dd>"
                            for name, text in items) + "</dl>"


def doc_html(doc):
    """A docstring as HTML: paragraphs, examples as code, parameter lists as definitions."""
    out = []
    for block in re.split(r"\n\s*\n", inspect.cleandoc(doc or "")):
        lines = block.splitlines()
        if not lines:
            continue
        runs, current, example = [], [], None
        for line in lines:
            is_example = line.lstrip().startswith((">>>", "... "))
            if example is not None and is_example != example:
                runs.append((example, current))
                current = []
            current.append(line)
            example = is_example
        runs.append((example, current))
        for is_example, run in runs:
            if is_example:
                out.append(f"<pre><code>{html.escape(textwrap.dedent(chr(10).join(run)))}</code></pre>")
            elif all(line.startswith("    ") for line in run):
                out.append(f"<pre><code>{html.escape(textwrap.dedent(chr(10).join(run)))}</code></pre>")
            elif PARAM.match(run[0]) or (len(run) > 1 and run[1].startswith("    ") and not run[0].startswith(" ")):
                out.append(definitions(run) or f"<p>{inline(' '.join(x.strip() for x in run))}</p>")
            else:
                out.append(f"<p>{inline(' '.join(x.strip() for x in run))}</p>")
    return "".join(out)


def signature(obj, drop_self=False):
    try:
        sig = inspect.signature(obj)
    except (TypeError, ValueError):
        return "(...)"
    if drop_self:
        params = list(sig.parameters.values())[1:]
        sig = sig.replace(parameters=params)
    return str(sig)


def entry(anchor, title, obj, drop_self=False):
    sig = "" if isinstance(obj, property) else signature(obj, drop_self)
    doc = obj.__doc__ if not isinstance(obj, property) else obj.fget.__doc__
    return (f'<section class="api" id="{anchor}"><h3><a href="#{anchor}">{html.escape(title)}</a>'
            f'<code class="sig">{html.escape(sig)}</code></h3>{doc_html(doc)}</section>')


def members(cls):
    """Public methods and properties, in the order the class defines them."""
    for name, value in vars(cls).items():
        if not name.startswith("_") and (inspect.isfunction(value) or isinstance(value, property)):
            yield name, value


def build_body():
    toc, parts = [], []

    def section(key, title, intro, entries):
        toc.append(f'<li><a href="#{key}">{title}</a></li>')
        parts.append(f'<h2 id="{key}">{title}</h2><p>{intro}</p>' + "".join(entries))

    section("start", "Start here", "One call from a table to an answer. Every function takes what "
            "<code>Graph</code> takes: a CSV or Excel path, a DataFrame, a list of rows.",
            [entry(f"tareco.{n}", f"tareco.{n}", getattr(tareco, n)) for n in START])
    graph = [entry("Graph", "tareco.Graph", tareco.Graph)]
    graph += [entry(f"Graph.{n}", f"g.{n}", v, drop_self=not isinstance(v, property))
              for n, v in members(tareco.Graph)]
    section("graph", "The graph", "Load once, then ask it questions.", graph)
    results = []
    for cls in RESULTS:
        results.append(entry(cls.__name__, cls.__name__, cls, drop_self=True))
        results += [entry(f"{cls.__name__}.{n}", f"{cls.__name__}.{n}", v, drop_self=not isinstance(v, property))
                    for n, v in members(cls)]
    section("results", "What comes back", "Answers print as plain language and turn into tables.", results)
    section("spark", "Spark", "<code>tareco.big</code>: the same questions on edge tables too big for one "
            "machine, run in the cluster.", [entry(f"big.{n}", f"tareco.big.{n}", getattr(big, n)) for n in SPARK])
    return (f'<h1>API reference</h1><p>tareco {tareco.__version__}. Written from the code itself.</p>'
            f'<ul class="toc">{"".join(toc)}</ul>' + "".join(parts))

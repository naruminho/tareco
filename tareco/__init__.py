"""tareco: from a table of connections to an interactive graph and plain-language answers.

Start here:

    import tareco
    tareco.show("friends.csv")                      # the interactive graph
    print(tareco.explain("friends.csv"))            # what it shows, in words
    tareco.report("friends.csv", "report.html")     # one file to send to someone

The table can be a CSV or Excel file, a pandas/polars/Spark DataFrame or a list
of pairs. Columns like from/to, source/target or origem/destino are found on
their own; a column such as valor/amount/quantity becomes the weight.

Then go further with ``g = tareco.Graph(data)``: g.explain(), g.profile(),
g.patterns(), g.communities(), g.pagerank(), g.shortest_path(a, b), and
tareco.timeline(...), tareco.project(...), tareco.neighborhood(...) for time,
two-sided tables and huge tables. tareco.doctor() checks your environment.

Money flows: Graph(statements, account=..., counterparty=..., keep=True) reads
bank statements; g.add_links(...) adds other kinds of links (devices, addresses);
g.splits(), g.unusual_amounts(), g.misfits(), g.near(), g.flows(), g.why(node) and
g.similar_to(node) point at what deserves a look, and tareco.records(...) takes you
back to the rows of your own tables.
"""

from . import algorithms, big, generators
from .errors import EdgeNotFound, HasCycle, NodeNotFound, NoPath, NotConnected, TarecoError
from .generators import (community_graph, complete_graph, cycle_graph, grid_graph, path_graph,
                         random_graph, scale_free_graph, small_world_graph, star_graph)
from .bipartite import project
from .around import neighborhood
from .checkup import doctor
from .temporal import Timeline, timeline
from .graph import Graph
from .i18n import set_language
from .excel import read_excel
from .io import DataWarning, GuessWarning, read_csv, read_json
from .quality import check
from .tracing import records
from .compare import compare

__version__ = "1.5.0"

_LOAD_OPTIONS = ("directed", "nodes", "source", "target", "node_id", "max_rows", "weight", "kind", "keep",
                 "account", "counterparty", "amount", "source_kind", "target_kind", "skip")


def _split(options):
    load = {k: options.pop(k) for k in _LOAD_OPTIONS if k in options}
    return load, options


def show(data, **options):
    """Draw anything that looks like a graph, in one line.

    ``data`` is whatever ``Graph`` accepts (CSV path, DataFrame, list of pairs,
    dict...). Loading options (``directed``, ``nodes``, ``source``, ``target``,
    ``node_id``) and view options (``color``, ``size``, ``label``, ``title``,
    ``dim``...) can be mixed freely.
    """
    g, view = _graph(data, options)
    g.show(**view)


def save(data, path, **options):
    """Like ``show``, but writes a standalone HTML file and returns its path."""
    g, view = _graph(data, options)
    return g.save(path, **view)


def explain(data, **options):
    """What the network in ``data`` shows, in plain language (see ``Graph.explain``).

    >>> print(tareco.explain("transfers.csv", lang="pt"))
    """
    g, rest = _graph(data, options)
    return g.explain(**rest)


def report(data, path=None, **options):
    """One shareable HTML file about ``data``: findings, tables and the graph (see ``Graph.report``)."""
    g, rest = _graph(data, options)
    return g.report(path, **rest)


def _graph(data, options):
    load, rest = _split(dict(options))
    if isinstance(data, (Graph, Timeline)) and not load:
        return data, rest
    return Graph(data, **load), rest


__all__ = [
    "Graph", "show", "save", "explain", "report", "read_csv", "read_json", "read_excel", "project", "neighborhood",
    "timeline", "records", "compare",
    "Timeline", "set_language", "doctor",
    "algorithms", "big", "generators",
    "complete_graph", "path_graph", "cycle_graph", "star_graph", "grid_graph", "random_graph",
    "scale_free_graph", "small_world_graph", "community_graph",
    "TarecoError", "NodeNotFound", "EdgeNotFound", "NoPath", "NotConnected", "HasCycle", "GuessWarning",
    "DataWarning", "check",
]

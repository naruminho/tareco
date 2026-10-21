"""tareco: graphs made simple, with zero dependencies.

>>> import tareco
>>> tareco.show("friends.csv")              # one line, interactive view
>>> g = tareco.Graph([("ana", "bia"), ("bia", "caio")])
>>> g.pagerank(), g.communities(), g.shortest_path("ana", "caio")
"""

from . import algorithms, generators
from .errors import EdgeNotFound, HasCycle, NodeNotFound, NoPath, NotConnected, TarecoError
from .generators import (community_graph, complete_graph, cycle_graph, grid_graph, path_graph,
                         random_graph, scale_free_graph, small_world_graph, star_graph)
from .graph import Graph
from .io import read_csv, read_json

__version__ = "1.1.0"

_LOAD_OPTIONS = ("directed", "nodes", "source", "target", "node_id", "max_rows")


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
    load, view = _split(options)
    g = data if isinstance(data, Graph) and not load else Graph(data, **load)
    g.show(**view)


def save(data, path, **options):
    """Like ``show``, but writes a standalone HTML file and returns its path."""
    load, view = _split(options)
    g = data if isinstance(data, Graph) and not load else Graph(data, **load)
    return g.save(path, **view)


__all__ = [
    "Graph", "show", "save", "read_csv", "read_json", "algorithms", "generators",
    "complete_graph", "path_graph", "cycle_graph", "star_graph", "grid_graph", "random_graph",
    "scale_free_graph", "small_world_graph", "community_graph",
    "TarecoError", "NodeNotFound", "EdgeNotFound", "NoPath", "NotConnected", "HasCycle",
]

"""A graph in one file, rows and all: save an investigation and pick it up later.

``g.save("case.tareco")`` writes everything tareco knows about the graph: the
nodes and links with their attributes, the rows kept behind each link, the
kinds of link and of node, the id prefixes and the weight column.
``tareco.load("case.tareco")`` (or ``Graph("case.tareco")``) gives the same
graph back, types included: dates stay dates, tuples stay tuples. The file is
gzip-compressed JSON, so anything that reads JSON can open it too.
"""

import datetime as dt
import gzip
import json
import os
from decimal import Decimal

from .errors import TarecoError

FORMAT = "tareco"
VERSION = 1   # bumped when an older tareco could no longer read the file
TAG = "$"     # marks a value JSON has no type for: {"$": "date", "v": "2026-03-01"}


def save(g, path):
    """Write ``g`` to ``path`` and return the absolute path."""
    from . import __version__
    data = {
        "format": FORMAT, "version": VERSION, "tareco": __version__,
        "directed": g.directed,
        "attrs": _pack(g.attrs),
        "nodes": [[_pack(n), _pack(d)] for n, d in g._nodes.items()],
        "links": [[_pack(u), _pack(v), _pack(d)] for u, v, d in g._edge_triples()],
        "rows": [[_pack(u), _pack(v), _pack(kind), _pack(row)] for u, v, kind, row in g._events],
    }
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    return os.path.abspath(path)


def load(path):
    """The graph saved in ``path`` by ``g.save("....tareco")``."""
    from .graph import Graph
    g = Graph()
    restore(g, path)
    return g


def restore(g, path):
    """Fill ``g`` with the graph saved in ``path``."""
    path = os.fspath(path)
    if not os.path.exists(path):
        raise TarecoError(f"file not found: {path}")
    try:
        with gzip.open(path, "rt", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError, EOFError):
        raise TarecoError(f"{path} is not a file saved by tareco") from None
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        raise TarecoError(f"{path} is not a file saved by tareco")
    if data.get("version", 0) > VERSION:
        raise TarecoError(f"{path} was saved by tareco {data.get('tareco')}; upgrade to open it: "
                          "pip install -U tareco")
    g._reset(bool(data["directed"]))
    g.attrs = _unpack(data["attrs"])
    for n, d in data["nodes"]:
        g._add_node(_unpack(n), _unpack(d))
    for u, v, d in data["links"]:
        g._add_edge(_unpack(u), _unpack(v), _unpack(d))
    g._events = [(_unpack(u), _unpack(v), _unpack(kind), _unpack(row)) for u, v, kind, row in data["rows"]]
    return g


def _pack(value):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if type(value).__module__ == "numpy" and hasattr(value, "item"):
        return _pack(value.item())
    if isinstance(value, dt.datetime):
        if hasattr(value, "to_pydatetime"):  # pandas Timestamp
            if value != value:  # NaT
                return None
            value = value.to_pydatetime()
        return {TAG: "datetime", "v": value.isoformat()}
    if isinstance(value, dt.date):
        return {TAG: "date", "v": value.isoformat()}
    if isinstance(value, dt.time):
        return {TAG: "time", "v": value.isoformat()}
    if isinstance(value, dt.timedelta):
        return {TAG: "timedelta", "v": value.total_seconds()}
    if isinstance(value, Decimal):
        return {TAG: "decimal", "v": str(value)}
    if isinstance(value, tuple):
        return {TAG: "tuple", "v": [_pack(x) for x in value]}
    if isinstance(value, frozenset):
        return {TAG: "frozenset", "v": [_pack(x) for x in value]}
    if isinstance(value, set):
        return {TAG: "set", "v": [_pack(x) for x in value]}
    if isinstance(value, list):
        return [_pack(x) for x in value]
    if isinstance(value, dict):
        if TAG not in value and all(isinstance(k, str) for k in value):
            return {k: _pack(x) for k, x in value.items()}
        return {TAG: "dict", "v": [[_pack(k), _pack(x)] for k, x in value.items()]}
    return str(value)


UNPACK = {
    "datetime": dt.datetime.fromisoformat,
    "date": dt.date.fromisoformat,
    "time": dt.time.fromisoformat,
    "timedelta": lambda v: dt.timedelta(seconds=v),
    "decimal": Decimal,
    "tuple": lambda v: tuple(_unpack(x) for x in v),
    "frozenset": lambda v: frozenset(_unpack(x) for x in v),
    "set": lambda v: {_unpack(x) for x in v},
    "dict": lambda v: {_unpack(k): _unpack(x) for k, x in v},
}


def _unpack(value):
    if isinstance(value, list):
        return [_unpack(x) for x in value]
    if isinstance(value, dict):
        if TAG in value:
            return UNPACK[value[TAG]](value["v"])
        return {k: _unpack(x) for k, x in value.items()}
    return value

"""Two-sided data (customers and products, accounts and devices) turned into one network.

Business data rarely comes as "who is linked to whom". It comes as "customer
bought product" or "account used device". Projecting it links the things you
care about through what they share: customers who buy the same products,
accounts that log in from the same devices.
"""

import warnings

from .errors import TarecoError
from .graph import Graph
from .io import MAX_ROWS, _missing, iter_table

METHODS = ("count", "jaccard", "newman")


class ProjectionWarning(UserWarning):
    """Some items were left out of a projection."""


def project(data, nodes=None, via=None, method="count", min_shared=1, max_item_size=1000,
            max_rows=MAX_ROWS):
    """Link the values of ``nodes`` that share values of ``via``.

    >>> purchases = [("ana", "rice"), ("bia", "rice"), ("bia", "coffee"), ("caio", "coffee")]
    >>> g = project(purchases)           # ana - bia (rice), bia - caio (coffee)

    data            a table: CSV path, pandas/polars/Spark DataFrame, rows or tuples.
    nodes, via      column names (default: the first and the second column).
    method          edge weight: "count" (shared items), "jaccard" (shared over
                    all items of the pair, 0 to 1) or "newman" (each shared item
                    counts 1/(people who have it - 1), so popular items matter less).
    min_shared      drop pairs that share fewer items than this.
    max_item_size   items shared by more nodes than this are skipped (a product
                    everybody buys links everybody to everybody, and costs
                    size^2 edges). None keeps them all.

    Other columns that never change for the same node become node attributes;
    numeric columns that change are summed into ``<column>_total``.
    """
    if method not in METHODS:
        raise TarecoError(f"method must be one of {METHODS}")
    columns, rows = iter_table(data, max_rows)
    if not columns:
        return Graph()
    if nodes is None:
        nodes = columns[0]
    if via is None:
        rest = [c for c in columns if c != nodes]
        if not rest:
            raise TarecoError("projection needs a second column to link through")
        via = rest[0]
    for col in (nodes, via):
        if col not in columns:
            raise TarecoError(f"no column {col!r}; columns are {columns}")

    order = {}
    items = {}
    constant = {}
    varying = set()
    totals = {}
    extra = [c for c in columns if c not in (nodes, via)]
    for row in rows:
        node, item = row.get(nodes), row.get(via)
        if _missing(node):
            continue
        order.setdefault(node, len(order))
        if not _missing(item):
            members = items.setdefault(item, {})
            members[node] = True
        attrs = constant.setdefault(node, {})
        for col in extra:
            value = row.get(col)
            if _missing(value):
                continue
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                totals.setdefault(node, {}).setdefault(col, 0)
                totals[node][col] += value
            if col in attrs and attrs[col] != value:
                varying.add(col)
            attrs.setdefault(col, value)

    g = Graph()
    g.attrs.update({"projected_on": via, "method": method})
    count_attr = f"n_{via}"
    per_node = {}
    for item, members in items.items():
        for node in members:
            per_node[node] = per_node.get(node, 0) + 1
    for node in sorted(order, key=order.get):
        attrs = {c: v for c, v in constant[node].items() if c not in varying}
        for col in varying:
            if col in totals.get(node, {}):
                attrs[f"{col}_total"] = totals[node][col]
        attrs[count_attr] = per_node.get(node, 0)
        g._add_node(node, attrs)
    _link(g, {item: list(members) for item, members in items.items()}, order, per_node, method,
          min_shared, max_item_size)
    return g


def project_graph(g, nodes, method="count", min_shared=1, max_item_size=1000):
    """``Graph.project``: keep ``nodes`` and link them through their shared neighbors."""
    if method not in METHODS:
        raise TarecoError(f"method must be one of {METHODS}")
    if callable(nodes):
        side = [n for n, attrs in g.nodes.items() if nodes(n, attrs)]
    else:
        side = [n for n in dict.fromkeys(nodes) if n in g]
    keep = set(side)
    order = {n: i for i, n in enumerate(side)}
    items = {}
    for item in g:
        if item in keep:
            continue
        members = [n for n in g._all_neighbors(item) if n in keep]
        if members:
            items[item] = sorted(members, key=order.get)
    per_node = {}
    for members in items.values():
        for node in members:
            per_node[node] = per_node.get(node, 0) + 1
    out = Graph()
    out.attrs.update(g.attrs)
    out.attrs.update({"method": method})
    for node in side:
        out._add_node(node, {**g.nodes[node], "n_items": per_node.get(node, 0)})
    _link(out, items, order, per_node, method, min_shared, max_item_size)
    return out


def _link(g, items, order, per_node, method, min_shared, max_item_size):
    pairs = {}
    skipped = 0
    for item, members in items.items():
        k = len(members)
        if k < 2:
            continue
        if max_item_size is not None and k > max_item_size:
            skipped += 1
            continue
        members = sorted(members, key=order.get)
        share = 1.0 / (k - 1)
        for i in range(k):
            a = members[i]
            for j in range(i + 1, k):
                key = (a, members[j])
                entry = pairs.get(key)
                if entry is None:
                    entry = pairs[key] = [0, 0.0, []]
                entry[0] += 1
                entry[1] += share
                if len(entry[2]) < 3:
                    entry[2].append(str(item))
    for (a, b), (shared, newman, examples) in pairs.items():
        if shared < min_shared:
            continue
        if method == "count":
            weight = shared
        elif method == "newman":
            weight = round(newman, 6)
        else:
            weight = round(shared / (per_node[a] + per_node[b] - shared), 6)
        g._add_edge(a, b, {"weight": weight, "shared": shared, "examples": ", ".join(examples)})
    if skipped:
        g.attrs["skipped_items"] = skipped
        warnings.warn(f"{skipped} items shared by more than {max_item_size} nodes were skipped; "
                      f"pass max_item_size=None to keep them", ProjectionWarning, stacklevel=3)

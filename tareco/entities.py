"""Nodes tied together by what they share (a device, a phone, an address): probably one person.

Accounts that log in from the same phone, customers at the same address: each
shared identifier ties them, and ties chain (a and b share a phone, b and c an
address). Identifiers shared by too many nodes (a branch computer, a shopping
mall address) tie nothing: they would glue everybody into one.
"""

from . import i18n
from .errors import TarecoError
from .indicators import _Text
from .io import _kinds_of


class Entity:
    __slots__ = ("members", "via")

    def __init__(self, members, via):
        self.members, self.via = members, via

    @property
    def size(self):
        return len(self.members)

    def __repr__(self):
        return f"{', '.join(map(str, self.members))} (through {', '.join(map(str, self.via))})"


class Entities(list):
    """Groups of nodes tied by shared identifiers, biggest first."""

    def __init__(self, items=(), g=None, lang="en", label=None):
        super().__init__(items)
        self._g = g
        self._lang = lang
        self._label = label

    def of(self, node):
        """The entity a node belongs to, or None."""
        return next((e for e in self if node in e.members), None)

    def __repr__(self):
        T = _Text(self._g, self._lang, self._label)
        lines = [T("entities_title")]
        for e in self:
            things = [f"{T.name(x)} ({self._g.nodes[x].get('kind')})" if self._g.nodes[x].get("kind")
                      else T.name(x) for x in e.via]
            lines.append("- " + T("entity_line", members=T.listing([T.name(m) for m in e.members], 6),
                                  things=T.listing(things, 3)))
        return "\n".join(lines) if self else lines[0] + "\n(" + T("nobody") + ")"

    def to_pandas(self):
        try:
            import pandas as pd
        except ImportError:
            raise TarecoError("to_pandas needs pandas: pip install pandas") from None
        return pd.DataFrame([{"entity": i + 1, "node": m, "size": e.size, "via": ", ".join(map(str, e.via))}
                             for i, e in enumerate(self) for m in e.members])

    def graph(self):
        """The graph with each entity as one node (``E1``, ``E2``...), its links and rows added up.

        Members keep their ids in the ``members`` attribute; links among members and
        to the identifiers that tie them disappear. Everything else (review, splits,
        similar_to) then works per entity instead of per node.
        """
        from .io import _is_number, _labels_something
        g = self._g
        name = {}
        for i, e in enumerate(self, 1):
            for m in e.members:
                name[m] = f"E{i}"
        ties = {x for e in self for x in e.via}
        out = g._new(g.directed)
        for i, e in enumerate(self, 1):
            kinds = {g.nodes[m].get("kind") for m in e.members}
            attrs = {"members": list(e.members), "size": e.size}
            if len(kinds) == 1 and None not in kinds:
                attrs["kind"] = kinds.pop()
            out._add_node(f"E{i}", attrs)
        for n, d in g.nodes.items():
            if n not in name and n not in ties:
                out._add_node(n, dict(d))
        for u, v, d in g._edge_triples():
            if u in ties or v in ties:
                continue
            a, b = name.get(u, u), name.get(v, v)
            if a == b:
                continue
            have = out._succ[a].get(b)
            if have is None:
                out._add_edge(a, b, dict(d))
                continue
            for k, x in d.items():  # two members' links to the same node become one
                if k == "kind":
                    kinds = _kinds_of(have)
                    if x not in kinds:
                        have["kind"] = tuple(sorted(kinds + (x,), key=str)) if kinds else x
                elif _is_number(x) and _is_number(have.get(k)) and not _labels_something(k):
                    have[k] += x
                else:
                    have.setdefault(k, x)
        out._events = [(name.get(u, u), name.get(v, v), k, r) for u, v, k, r in g._events
                       if name.get(u, u) != name.get(v, v) and u not in ties and v not in ties]
        return out


def entities(g, via=None, max_share=10, lang=None, label=None):
    """Groups of nodes tied together by identifiers they share: probably one person.

    via         the node kinds that identify ("device", ["phone", "address"]).
                Default: the kinds tied to others only by links without direction.
    max_share   identifiers shared by more nodes than this tie nothing (a branch
                computer, a mall's address).
    """
    T = _Text(g, lang, label)
    known = g.attrs.get("link_kinds") or {}
    plain = {k for k, v in known.items() if not v.get("directed")}
    if via is None:
        flowing = {x for u, v, d in g._edge_triples() if not (set(_kinds_of(d)) or {None}) <= plain
                   for x in (u, v)}
        kinds = {g.nodes[x].get("kind") for u, v, d in g._edge_triples() if set(_kinds_of(d)) & plain
                 for x in (u, v) if x not in flowing}
        kinds -= {g.nodes[x].get("kind") for x in flowing}  # an account without transfers is still an account
        kinds.discard(None)
        if not kinds:
            raise TarecoError("no identifiers to tie nodes by; add them with add_links(..., kind=...) "
                              "or pass via=\"device\"")
    else:
        kinds = {via} if isinstance(via, str) else set(via)
    ids = [x for x, d in g._nodes.items() if d.get("kind") in kinds]
    parent = {}

    def root(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    used = {}
    for x in ids:
        holders = [y for y in g._all_neighbors(x) if y != x and g._nodes[y].get("kind") not in kinds]
        if len(holders) < 2 or len(holders) > max_share:
            continue
        for y in holders:
            parent.setdefault(y, y)
        first = root(holders[0])
        for y in holders[1:]:
            parent[root(y)] = first
        used[x] = holders
    groups = {}
    for y in parent:
        groups.setdefault(root(y), []).append(y)
    order = {n: i for i, n in enumerate(g)}
    found = []
    for members in groups.values():
        members.sort(key=order.get)
        mine = set(members)
        tie = sorted((x for x, holders in used.items() if mine & set(holders)), key=order.get)
        found.append(Entity(members, tie))
    found.sort(key=lambda e: (-e.size, order[e.members[0]]))
    return Entities(found, g, T.lang, label)

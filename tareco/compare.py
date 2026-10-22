"""Two networks side by side (two months, two regions, before and after): what changed, in words."""

from . import i18n
from .graph import Graph, _weight_fn
from .indicators import _Text
from .insights import Explanation, Finding, Profiles

GROUP_MIN = 5


def compare(before, after, lang=None, label=None, top=3):
    """What changed from ``before`` to ``after``, in plain words.

    Nodes and links that came and went, the change in total weight, nodes that
    rose in importance or jumped in connections, groups that formed, vanished or
    merged, and links that grew the most. Each finding keeps the nodes it is about.
    """
    if not isinstance(before, Graph) or not isinstance(after, Graph):
        raise TypeError("compare takes two graphs; for a timeline use timeline.compare(period, period)")
    T = _Text(after, lang, label)
    num = T.num
    names = lambda nodes: T.listing([T.name(x) if x in after else _plain_name(before, x, label)  # noqa: E731
                                     for x in nodes], top)
    out = []
    n1, n2, m1, m2 = len(before), len(after), before.edge_count, after.edge_count
    out.append(Finding("sizes", T("cmp_overview", n1=num(n1), n2=num(n2), dn=_signed(n2 - n1, T),
                                  m1=num(m1), m2=num(m2), dm=_signed(m2 - m1, T))))
    w1, w2 = _total(before), _total(after)
    if w1 is not None and w2 is not None and w1 > 0:
        weight = i18n.metric_name(after.attrs.get("weight") or before.attrs.get("weight") or "weight", T.lang)
        out.append(Finding("total", T("cmp_weight", weight=weight, w1=num(w1), w2=num(w2),
                                      pct=_signed_pct((w2 - w1) / w1, T.lang))))

    deg1, deg2 = before.degree(), after.degree()
    new = sorted((x for x in after if x not in before), key=lambda x: -deg2[x])
    gone = sorted((x for x in before if x not in after), key=lambda x: -deg1[x])
    if new:
        key = "cmp_new_one" if len(new) == 1 else "cmp_new"
        out.append(Finding("new_nodes", T(key, k=num(len(new)), names=names(new)), new))
    if gone:
        key = "cmp_gone_one" if len(gone) == 1 else "cmp_gone"
        out.append(Finding("gone_nodes", T(key, k=num(len(gone)), names=names(gone)), gone))

    both = [x for x in after if x in before]
    if both and before.edge_count and after.edge_count:
        r1, r2 = _ranks(before), _ranks(after)
        risers = sorted((x for x in both if r1[x] >= 5 * r2[x] and r2[x] <= max(3, len(after) // 20)),
                        key=lambda x: (r2[x] / r1[x], r2[x]))[:top]
        for x in risers:
            out.append(Finding("rose", T("cmp_rose", name=T.name(x), a=num(r1[x]), b=num(r2[x])), [x]))
        jumps = sorted((x for x in both if deg2[x] >= max(5, 3 * max(1, deg1[x])) and x not in risers),
                       key=lambda x: -(deg2[x] - deg1[x]))[:top]
        for x in jumps:
            out.append(Finding("jump", T("cmp_jump", name=T.name(x), a=num(deg1[x]), b=num(deg2[x])),
                               [x] + list(after._all_neighbors(x))))

    out += _group_changes(before, after, T, top)
    out += _grown_links(before, after, T, top)
    return Explanation(out, Profiles(), T.lang, title=T("cmp_title"))


def _plain_name(g, node, label):
    if label is not None and g.nodes[node].get(label) is not None:
        return str(g.nodes[node][label])
    return str(node)


def _signed(k, T):
    return ("+" if k > 0 else "") + T.num(k)


def _signed_pct(share, lang):
    return ("+" if share > 0 else "-" if share < 0 else "") + i18n.percent(abs(share), lang)


def _total(g):
    weight = g.attrs.get("weight") or ("weight" if any("weight" in d for _, _, d in g._edge_triples()) else None)
    if not weight:
        return None
    wt = _weight_fn("weight", g)
    return sum(wt(d) for _, _, d in g._edge_triples())


def _ranks(g):
    rank = g.pagerank()
    order = sorted(g, key=lambda x: (-rank[x], str(x)))
    return {x: i + 1 for i, x in enumerate(order)}


def _group_changes(before, after, T, top):
    if not before.edge_count or not after.edge_count:
        return []
    old_all, new_all = before.communities(), after.communities()
    # groups only mean something when the network really splits into groups
    old_real = before.modularity(old_all) >= 0.3
    new_real = after.modularity(new_all) >= 0.3
    old = [c for c in old_all if len(c) >= GROUP_MIN] if old_real else []
    new = [c for c in new_all if len(c) >= GROUP_MIN] if new_real else []
    rank = after.pagerank()

    def around(c):
        return T.listing([T.name(x) for x in sorted(c, key=lambda x: (-rank.get(x, 0), str(x)))[:3]])

    out = []
    for c in new:
        parents = [q for q in old if len(c & q) >= 0.6 * len(q)]
        best = max((len(c & q) / len(c | q) for q in old), default=0)
        if len(parents) >= 2:
            heads = [sorted(q & c, key=lambda x: (-rank.get(x, 0), str(x)))[0] for q in parents[:2]]
            out.append((len(c), Finding("merge", T("cmp_merge", a=T.name(heads[0]), b=T.name(heads[1])),
                                        sorted(c, key=str))))
        elif best < 0.2:
            out.append((len(c), Finding("new_group", T("cmp_new_group", k=T.num(len(c)), names=around(c)),
                                        sorted(c, key=str))))
    for q in old:
        if max((len(q & c) / len(q | c) for c in new), default=0) < 0.2 and \
                sum(1 for x in q if x in after) < 0.5 * len(q):
            names = T.listing([_plain_name(before, x, T.label) for x in sorted(q, key=str)[:3]])
            out.append((len(q), Finding("gone_group", T("cmp_gone_group", k=T.num(len(q)), names=names),
                                        sorted(q, key=str))))
    out.sort(key=lambda f: -f[0])
    return [f for _, f in out[:top + 1]]


def _grown_links(before, after, T, top):
    if _total(before) is None or _total(after) is None:
        return []
    w1, w2 = _weight_fn("weight", before), _weight_fn("weight", after)
    grown = []
    for u, v, d in after._edge_triples():
        if before.has_edge(u, v):
            a, b = w1(before._succ[u][v]), w2(d)
            if isinstance(a, (int, float)) and isinstance(b, (int, float)) and a > 0 and b >= 3 * a:
                grown.append((b - a, u, v, a, b))
    grown.sort(key=lambda t: (-t[0], str(t[1])))
    return [Finding("grew", T("cmp_grew", a=T.name(u), b=T.name(v), x=T.num(x), y=T.num(y)), [u, v])
            for _, u, v, x, y in grown[:top]]

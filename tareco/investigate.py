"""One node at a time: what stands out about it, and which other nodes behave like it."""

import math

from . import i18n
from .errors import TarecoError
from .indicators import _median, _Text, flow_kinds, misfits, near, splits, time_column, parse_times, \
    unusual_amounts
from .insights import Explanation, Finding, Profiles, profile
from .io import _is_number, _kinds_of, _missing
from .patterns import _flow_part, find_patterns

INVOLVES = ("cycle", "chain", "clique", "back_and_forth")    # the text names every node in it
CENTERED = ("fan_in", "fan_out", "pass_through", "star", "shared")  # the text is about nodes[0]


# -------------------------------------------------------------------------- why

def why(g, node, watch=None, lang=None, label=None):
    """What stands out about ``node``, in plain words, with the nodes each line is about.

    watch   a list to check closeness to (flagged nodes, known cases), as in ``near``.
    """
    g._check(node)
    T = _Text(g, lang, label)
    name = T.name(node)
    attrs = g._nodes[node]
    kind = attrs.get("kind")
    findings = []
    shown = [(k, v) for k, v in attrs.items() if k not in ("kind", "hop") and not _missing(v)][:5]
    listed = ", ".join(f"{k} {T.num(v) if _is_number(v) else v}" for k, v in shown)
    if kind is not None:
        findings.append(Finding("identity", T("why_identity", name=name, kind=kind,
                                              attrs=(": " + listed) if listed else ""), [node]))
    elif listed:
        findings.append(Finding("identity", T("why_attrs", name=name, attrs=listed), [node]))
    notable = len(findings)

    flow = _flow_part(g)
    nbrs = [y for y in g._all_neighbors(node) if y != node]
    if g.directed and node in flow:
        from .graph import _weight_fn
        wt = _weight_fn("weight", g)
        outs = [(v, d) for v, d in flow._succ[node].items() if v != node]
        ins = [(u, d) for u, d in flow._pred[node].items() if u != node]
        findings.append(Finding("flows", T("why_flows", out=T.num(sum(wt(d) for _, d in outs)),
                                           k_out=T.num(len(outs)), inn=T.num(sum(wt(d) for _, d in ins)),
                                           k_in=T.num(len(ins))),
                                [node] + [v for v, _ in outs] + [u for u, _ in ins]))
    else:
        findings.append(Finding("links", T("why_links", k=T.num(len(nbrs))), [node] + nbrs))
    notable = len(findings)

    peers = [len(set(g._all_neighbors(x)) - {x}) for x, d in g._nodes.items() if d.get("kind") == kind]
    typical = _median([p for p in peers if p > 0] or [0])
    if typical and len(nbrs) >= max(5, 3 * typical):
        findings.append(Finding("busy", T("why_busy", times=T.num(round(len(nbrs) / typical, 1)),
                                          kind=kind or i18n.text(T.lang, "node_word"), d=T.num(len(nbrs)),
                                          median=T.num(typical)), [node] + nbrs))
    if g.edge_count:
        rank = g.pagerank()
        position = sorted(rank.values(), reverse=True).index(rank[node])
        share = (position + 1) / len(g)
        if share <= 0.05 and len(g) >= 20:
            findings.append(Finding("rank", T("why_rank", pct=i18n.percent(share, T.lang)), [node]))
        comms = g.communities()
        groups = profile(g, lang=T.lang, label=label, communities=comms, pagerank=rank)
        mine = next((p for p in groups if node in p.members), None)
        if mine is not None and len(groups) > 1 and mine.size >= 3:
            traits = mine.summary(limit=1)
            findings.append(Finding("group", T("why_group", group=mine.name, traits=f": {traits}" if traits else ""),
                                    sorted(mine.members, key=lambda x: -rank.get(x, 0)), mine.label))
            other = {p.label: p.name for p in groups}
            group_of = {x: p.label for p in groups for x in p.members}
            mates = [y for y in nbrs if g._nodes[y].get("kind") == kind]  # shops bridge everybody
            touched = list(dict.fromkeys(group_of[y] for y in mates if group_of.get(y) not in (None, mine.label)))
            if len(touched) >= 2:
                names = [mine.name] + [other[t] for t in touched[:3]]
                findings.append(Finding("broker", T("broker", name=name, groups=T.join(names)), [node] + nbrs))

    for p in find_patterns(g, lang=T.lang, label=label, limit=200):
        if p.kind in INVOLVES and node in p.nodes:
            findings.append(Finding(p.kind, p.text, p.nodes))
        elif p.kind in CENTERED and p.nodes and p.nodes[0] == node and _exclusive(p):
            findings.append(Finding(p.kind, p.text, p.nodes))
        elif p.kind in ("fan_in", "fan_out") and node in p.nodes[1:] and _exclusive(p) \
                and sum(1 for f in findings if f.kind == "part_of") < 2:
            findings.append(Finding("part_of", T("why_part_of", text=p.text), p.nodes))

    if g.attrs.get("kept"):
        for p in unusual_amounts(g, lang=T.lang, label=label, limit=1000):
            if p.nodes[0] == node:
                findings.append(Finding(p.kind, p.text, p.nodes))
        try:
            for p in splits(g, lang=T.lang, label=label, top=1000):
                if p.nodes[0] == node:
                    findings.append(Finding(p.kind, p.text, p.nodes))
        except TarecoError:
            pass  # no dates
    for p in misfits(g, lang=T.lang, label=label, limit=1000):
        if p.nodes[0] == node:
            findings.append(Finding(p.kind, p.text, p.nodes))

    things, others = _shares(g, node)
    if things:
        shown_things = [f"{T.name(y)} ({g._nodes[y].get('kind')})" for y in things[:3]]
        findings.append(Finding("shares", T("why_shares", things=T.join(shown_things),
                                            others=T.listing([T.name(z) for z in others], 5)),
                                [node] + things + others))
    if watch is not None:
        for p in near(g, watch, lang=T.lang, label=label, limit=10 ** 6, kinds=[kind]):
            if p.nodes[0] == node:
                findings.append(Finding("near", p.text, p.nodes))
    if g.attrs.get("kept"):
        rows = [e[3] for e in g._events if e[0] == node or e[1] == node]
        column = time_column(rows) if rows else None
        if column:
            whens = [w for w in parse_times([r.get(column) for r in rows]) if w is not None]
            if whens:
                findings.append(Finding("seen", T("why_seen", first=T.date(min(whens)), last=T.date(max(whens)),
                                                  k=T.num(len(rows))), [node]))
    if len(findings) == notable:
        findings.append(Finding("nothing", T("why_nothing", name=name), [node]))
    return Explanation(findings, Profiles(), T.lang, title=T("why_title", name=name))


def _exclusive(p):
    """A fan-in or fan-out worth telling: most partners deal with nobody else (not a shop's customers)."""
    if p.kind not in ("fan_in", "fan_out"):
        return True
    k = p.details["in"] if p.kind == "fan_in" else p.details["out"]
    return p.details.get("only", 0) >= max(3, 0.5 * k)


def _shares(g, node):
    """Nodes of another kind that ``node`` shares with nodes of its own kind (a device, an address)."""
    kind = g._nodes[node].get("kind")
    if kind is None:
        return [], []
    known = g.attrs.get("link_kinds") or {}
    plain = {k for k, v in known.items() if not v.get("directed")}
    things, others = [], []
    for y in g._all_neighbors(node):
        if y == node or g._nodes[y].get("kind") in (None, kind):
            continue
        d = g._succ[node].get(y) or g._succ[y].get(node) or {}
        if plain and not set(_kinds_of(d)) & plain:
            continue
        mates = [z for z in g._all_neighbors(y) if z != node and g._nodes[z].get("kind") == kind]
        if mates:
            things.append(y)
            others.extend(z for z in mates if z not in others)
    return things, others


# ------------------------------------------------------------------- similar_to

class SimilarNode:
    __slots__ = ("node", "score", "reasons")

    def __init__(self, node, score, reasons):
        self.node, self.score, self.reasons = node, score, reasons

    def __repr__(self):
        return f"{self.node!r} ({self.score})"


class Similar(list):
    """Nodes that behave like the ones given, most alike first, each with its reasons."""

    def __init__(self, items=(), title="", lang="en", g=None, label=None):
        super().__init__(items)
        self.title = title
        self._lang = lang
        self._g = g
        self._label = label

    @property
    def nodes(self):
        return [s.node for s in self]

    def __repr__(self):
        T = _Text(self._g, self._lang, self._label)
        lines = [self.title]
        for s in self:
            reasons = "; ".join(s.reasons) if s.reasons else T("similar_none")
            lines.append("- " + T("similar_line", name=T.name(s.node), score=T.num(s.score), reasons=reasons))
        return "\n".join(lines)

    def to_pandas(self):
        try:
            import pandas as pd
        except ImportError:
            raise TarecoError("to_pandas needs pandas: pip install pandas") from None
        return pd.DataFrame([{"node": s.node, "score": s.score, "reasons": "; ".join(s.reasons),
                              **self._g.nodes[s.node]} for s in self])


FEATURES = ("out_links", "in_links", "out_amount", "in_amount", "pass_through", "only_senders",
            "only_receivers", "splits", "unusual", "shared", "cycles", "chains", "typical_amount")


def role_features(g):
    """``{node: {feature: value}}``: how each node behaves in the flow, not who it is."""
    from .graph import _weight_fn
    flow = _flow_part(g)
    wt = _weight_fn("weight", g)
    counts = {f: {} for f in ("cycles", "chains", "splits", "unusual")}
    for p in find_patterns(g, kinds=["cycle", "chain"], limit=10 ** 6) if g.directed else []:
        bucket = counts["cycles" if p.kind == "cycle" else "chains"]
        for x in (p.nodes if p.kind == "cycle" else p.nodes[1:-1]):
            bucket[x] = bucket.get(x, 0) + 1
    typical = {}
    if g.attrs.get("kept"):
        for p in unusual_amounts(g, limit=10 ** 6):
            counts["unusual"][p.nodes[0]] = counts["unusual"].get(p.nodes[0], 0) + 1
        try:
            for p in splits(g, top=10 ** 6):
                counts["splits"][p.nodes[0]] = counts["splits"].get(p.nodes[0], 0) + p.details["count"]
        except TarecoError:
            pass
        from .indicators import transfers
        sent = {}
        for t in transfers(g):
            sent.setdefault(t.u, []).append(t.amount)
        typical = {x: _median(v) for x, v in sent.items()}
    out = {}
    for x in g:
        has = x in flow._nodes
        if flow.directed and has:
            succ = [v for v in flow._succ[x] if v != x]
            pred = [u for u in flow._pred[x] if u != x]
            w_out = sum(wt(flow._succ[x][v]) for v in succ)
            w_in = sum(wt(flow._pred[x][u]) for u in pred)
            only_s = sum(1 for u in pred if len(flow._succ[u]) == 1) / len(pred) if pred else 0.0
            only_r = sum(1 for v in succ if len(flow._pred[v]) == 1) / len(succ) if succ else 0.0
        else:
            nb = [y for y in (flow._succ[x] if has else ()) if y != x]
            succ = pred = nb
            w_out = w_in = sum(wt(flow._succ[x][y]) for y in nb)
            only_s = only_r = 0.0
        things, _ = _shares(g, x)
        if x not in typical and has and succ:
            typical[x] = _median([wt(flow._succ[x][v]) for v in succ])
        out[x] = {
            "out_links": math.log1p(len(succ)), "in_links": math.log1p(len(pred)),
            "out_amount": math.log1p(max(0, w_out)), "in_amount": math.log1p(max(0, w_in)),
            "pass_through": min(w_in, w_out) / max(w_in, w_out) if max(w_in, w_out) > 0 else 0.0,
            "only_senders": only_s, "only_receivers": only_r,
            "splits": math.log1p(counts["splits"].get(x, 0)), "unusual": math.log1p(counts["unusual"].get(x, 0)),
            "shared": math.log1p(len(things)),
            "cycles": math.log1p(counts["cycles"].get(x, 0)), "chains": math.log1p(counts["chains"].get(x, 0)),
            "typical_amount": math.log1p(max(0, typical.get(x, 0) or 0)),
        }
    return out


def similar_to(g, nodes, n=10, lang=None, label=None):
    """The nodes that behave most like ``nodes`` (one or a few known cases), with the reasons.

    Behavior means how a node sits in the flow (links in and out, amounts,
    passing money on, loops, chains, amounts just under a limit, unusually large
    transfers, things shared with others), not its attributes. Only nodes of the
    same kind are compared.
    """
    seeds = list(nodes) if isinstance(nodes, (list, tuple, set, frozenset)) else [nodes]
    for x in seeds:
        g._check(x)
    T = _Text(g, lang, label)
    kind = g._nodes[seeds[0]].get("kind")
    feats = role_features(g)
    pool = [x for x in g if g._nodes[x].get("kind") == kind]
    scale = {}
    for f in FEATURES:
        values = [feats[x][f] for x in pool]
        med = _median(values)
        mad = _median([abs(v - med) for v in values]) * 1.4826
        if mad == 0:
            mean = sum(values) / len(values)
            mad = math.sqrt(sum((v - mean) ** 2 for v in values) / len(values))
        scale[f] = (med, mad)

    def z(x):
        out = {}
        for f in FEATURES:
            med, mad = scale[f]
            out[f] = 0.0 if mad == 0 else max(-6.0, min(6.0, (feats[x][f] - med) / mad))
        return out

    center = {f: sum(z(x)[f] for x in seeds) / len(seeds) for f in FEATURES}
    weights = {f: 1 + abs(center[f]) for f in FEATURES}
    total = sum(weights.values())
    shared_kind = _shared_kind(g, seeds)
    scored = []
    for x in pool:
        if x in seeds:
            continue
        zx = z(x)
        dist = math.sqrt(sum(weights[f] * (center[f] - zx[f]) ** 2 for f in FEATURES) / total)
        reasons = []
        for f in sorted(FEATURES, key=lambda f: -abs(center[f])):
            # what is special about the seeds, and this node shares
            if abs(center[f]) >= 1.5 and zx[f] * (1 if center[f] > 0 else -1) >= 1.0:
                key = _reason_key(f, center[f])
                if key:
                    reasons.append(T(key, kind=shared_kind or "") if key == "sim_shared" else T(key))
        scored.append((round(1 / (1 + dist), 2), x, reasons[:4]))
    order = {x: i for i, x in enumerate(g)}
    scored.sort(key=lambda s: (-s[0], order[s[1]]))
    names = T.join([T.name(x) for x in seeds])
    return Similar([SimilarNode(x, score, reasons) for score, x, reasons in scored[:n]],
                   T("similar_title", name=names), T.lang, g, label)


def _reason_key(feature, direction):
    if direction > 0:
        return "sim_" + feature
    if feature == "typical_amount":
        return "sim_typical_amount_low"
    if feature in ("out_links", "in_links"):
        return "sim_links_low"
    return None


def _shared_kind(g, seeds):
    for x in seeds:
        things, _ = _shares(g, x)
        if things:
            return g._nodes[things[0]].get("kind")
    return None

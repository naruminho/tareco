"""Shapes worth a second look: loops, fan-ins, relays, chains, stars and cliques.

Every pattern is described in plain network terms (who sends to whom, how
much goes around), so it applies to orders, messages, supply chains or any
other flow.
"""

from . import i18n

KINDS = ("cycle", "fan_in", "fan_out", "pass_through", "chain", "back_and_forth", "star", "clique")
STEP_BUDGET = 2_000_000   # search steps for cycles and cliques, so big graphs stay fast


class Pattern:
    __slots__ = ("kind", "nodes", "score", "details", "text")

    def __init__(self, kind, nodes, score, details, text):
        self.kind = kind
        self.nodes = nodes
        self.score = score
        self.details = details
        self.text = text

    def to_dict(self):
        return {k: getattr(self, k) for k in self.__slots__}

    def __repr__(self):
        return self.text


class Patterns(list):
    """Found patterns, strongest first within each kind."""

    def of(self, kind):
        return Patterns(p for p in self if p.kind == kind)

    def __repr__(self):
        return "\n".join(f"- {p.text}" for p in self) if self else "(no patterns)"

    def to_pandas(self):
        from .errors import TarecoError
        try:
            import pandas as pd
        except ImportError:
            raise TarecoError("to_pandas needs pandas: pip install pandas") from None
        return pd.DataFrame([{"kind": p.kind, "score": p.score, "nodes": list(p.nodes), "text": p.text}
                             for p in self])


def find_patterns(g, kinds=None, lang=None, limit=10, weight="weight", max_cycle=4, label=None,
                  min_fan=5):
    """Look for every pattern kind (or only ``kinds``) and describe what was found.

    limit       most patterns kept per kind.
    max_cycle   longest loop searched (3 to 6 is sensible).
    min_fan     how many senders/receivers make a fan-in, fan-out or relay.
    """
    lang = i18n.get_language(lang)
    wanted = KINDS if kinds is None else tuple(kinds)
    unknown = [k for k in wanted if k not in KINDS]
    if unknown:
        from .errors import TarecoError
        raise TarecoError(f"unknown pattern kinds {unknown}; choose from {KINDS}")
    ctx = _Context(g, lang, weight, label)
    found = Patterns()
    for kind in wanted:
        if kind in ("cycle", "fan_in", "fan_out", "pass_through", "chain", "back_and_forth") and not g.directed:
            continue
        if kind == "cycle":
            found += _cycles(ctx, max_cycle, limit)
        elif kind in ("fan_in", "fan_out", "pass_through"):
            found += _fans(ctx, kind, min_fan, limit)
        elif kind == "chain":
            found += _chains(ctx, limit)
        elif kind == "back_and_forth":
            found += _back_and_forth(ctx, limit)
        elif kind == "star":
            found += _stars(ctx, limit)
        else:
            found += _cliques(ctx, limit)
    return found


class _Context:
    def __init__(self, g, lang, weight, label):
        self.g = g
        self.lang = lang
        self.weight = weight
        self.label = label
        self.weighted = bool(weight) and any(_is_number(d.get(weight)) for _, _, d in g._edge_triples())

    def w(self, u, v):
        value = self.g._succ[u][v].get(self.weight) if self.weight else None
        return value if _is_number(value) else 1

    def name(self, node):
        if self.label is not None:
            value = self.g.nodes[node].get(self.label)
            if value is not None:
                return str(value)
        return str(node)

    def text(self, key, **kw):
        return i18n.text(self.lang, key, **kw)

    def num(self, value):
        return i18n.number(value, self.lang)


def _is_number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v


def _cycles(ctx, max_len, limit):
    g = ctx.g
    order = {n: i for i, n in enumerate(g)}
    cycles = []
    steps = 0
    for start in g:
        rank = order[start]
        stack = [(start, iter(g._succ[start]))]
        path = [start]
        on_path = {start}
        while stack and steps < STEP_BUDGET:
            node, nbrs = stack[-1]
            advanced = False
            for v in nbrs:
                steps += 1
                if v == start and len(path) >= 3:
                    cycles.append(list(path))
                elif v not in on_path and order[v] > rank and len(path) < max_len:
                    stack.append((v, iter(g._succ[v])))
                    path.append(v)
                    on_path.add(v)
                    advanced = True
                    break
            if not advanced:
                stack.pop()
                on_path.discard(path.pop())
        if steps >= STEP_BUDGET:
            break
    scored = []
    for c in cycles:
        hops = list(zip(c, c[1:] + c[:1]))
        bottleneck = min(ctx.w(u, v) for u, v in hops)
        scored.append((bottleneck if ctx.weighted else 0, -len(c), c, bottleneck))
    scored.sort(key=lambda t: (-t[0], -t[1]))
    out = []
    for score, _, c, bottleneck in scored[:limit]:
        names = [ctx.name(x) for x in c]
        route = i18n.join(names, ctx.lang)
        loop = ctx.text("route_sep").join(names + [names[0]])
        text = ctx.text("cycle", nodes=route, route=loop)
        if ctx.weighted:
            text += " " + ctx.text("cycle_amount", amount=ctx.num(bottleneck))
        out.append(Pattern("cycle", c, score, {"length": len(c), "bottleneck": bottleneck}, text))
    return out


def _fans(ctx, kind, min_fan, limit):
    g = ctx.g
    out = []
    for x in g:
        senders = [u for u in g._pred[x] if u != x]
        receivers = [v for v in g._succ[x] if v != x]
        k_in, k_out = len(senders), len(receivers)
        if kind == "fan_in" and k_in >= min_fan and k_out * 4 <= k_in:
            out.append((k_in, x, senders, k_in, k_out))
        elif kind == "fan_out" and k_out >= min_fan and k_in * 4 <= k_out:
            out.append((k_out, x, receivers, k_in, k_out))
        elif kind == "pass_through" and k_in >= min_fan and k_out >= min_fan:
            got = sum(ctx.w(u, x) for u in senders)
            gave = sum(ctx.w(x, v) for v in receivers)
            if got and 0.8 <= gave / got <= 1.25:
                out.append((min(k_in, k_out), x, senders + receivers, k_in, k_out, got, gave))
    out.sort(key=lambda t: -t[0])
    patterns = []
    nobody = ctx.text("nobody")
    for item in out[:limit]:
        score, x, others = item[0], item[1], item[2]
        k_in, k_out = item[3], item[4]
        if kind == "fan_in":
            text = ctx.text("collector", name=ctx.name(x), k=ctx.num(k_in), out=ctx.num(k_out) if k_out else nobody)
        elif kind == "fan_out":
            text = ctx.text("distributor", name=ctx.name(x), k=ctx.num(k_out), inn=ctx.num(k_in) if k_in else nobody)
        else:
            got, gave = item[5], item[6]
            key = "pass_through_amount" if ctx.weighted else "pass_through"
            text = ctx.text(key, name=ctx.name(x), k_in=ctx.num(k_in), k_out=ctx.num(k_out),
                            got=ctx.num(got), gave=ctx.num(gave))
        patterns.append(Pattern(kind, [x] + others, score, {"in": k_in, "out": k_out}, text))
    return patterns


def _chains(ctx, limit):
    """Runs of intermediaries: nodes with exactly one sender and one receiver, in a row."""
    g = ctx.g

    def middle(x):
        return len(g._pred[x]) == 1 and len(g._succ[x]) == 1 and x not in g._succ[x]

    seen = set()
    chains = []
    for x in g:
        if x in seen or not middle(x):
            continue
        back, cur, local = [], x, {x}
        first = None
        while True:
            p = next(iter(g._pred[cur]))
            if p in local:
                break  # a closed loop of intermediaries has no ends
            local.add(p)
            if not middle(p):
                first = p
                break
            back.append(p)
            cur = p
        forward, cur, last = [], x, None
        while first is not None:
            n = next(iter(g._succ[cur]))
            if n in local:
                break
            local.add(n)
            if not middle(n):
                last = n
                break
            forward.append(n)
            cur = n
        inner = back[::-1] + [x] + forward
        seen.update(inner)
        if first is not None and last is not None and len(inner) >= 2:
            chains.append([first] + inner + [last])
    chains.sort(key=len, reverse=True)
    out = []
    for c in chains[:limit]:
        names = [ctx.name(x) for x in c]
        text = ctx.text("chain", route=ctx.text("route_sep").join(names), k=ctx.num(len(c) - 2))
        out.append(Pattern("chain", c, len(c) - 2, {"length": len(c) - 1}, text))
    return out


def _back_and_forth(ctx, limit):
    g = ctx.g
    pairs = []
    for u, v, _ in g._edge_triples():
        if u == v or not g.has_edge(v, u) or str(u) > str(v):
            continue
        a, b = ctx.w(u, v), ctx.w(v, u)
        if a and b and 0.8 <= a / b <= 1.25:
            pairs.append((min(a, b), u, v, a, b))
    pairs.sort(key=lambda t: -t[0])
    out = []
    if not ctx.weighted:
        return out
    for score, u, v, a, b in pairs[:limit]:
        text = ctx.text("back_and_forth", a=ctx.name(u), b=ctx.name(v), x=ctx.num(a), y=ctx.num(b))
        out.append(Pattern("back_and_forth", [u, v], score, {"there": a, "back": b}, text))
    return out


def _stars(ctx, limit, min_leaves=8):
    g = ctx.g
    out = []
    for x in g:
        leaves = [y for y in g._all_neighbors(x) if y != x and len(set(g._all_neighbors(y)) - {y}) == 1]
        if len(leaves) >= min_leaves:
            out.append((len(leaves), x, leaves))
    out.sort(key=lambda t: -t[0])
    return [Pattern("star", [x] + leaves, k, {"leaves": k},
                    ctx.text("star", name=ctx.name(x), k=ctx.num(k)))
            for k, x, leaves in out[:limit]]


def _cliques(ctx, limit, min_size=4):
    """Maximal cliques (Bron-Kerbosch with pivoting, degeneracy order), direction ignored."""
    g = ctx.g
    nbrs = {u: set(g._all_neighbors(u)) - {u} for u in g}
    order = sorted(g, key=lambda u: len(nbrs[u]))
    position = {u: i for i, u in enumerate(order)}
    found = []
    steps = [0]

    def expand(r, p, x):
        steps[0] += 1
        if steps[0] > STEP_BUDGET:
            return
        if not p and not x:
            if len(r) >= min_size:
                found.append(list(r))
            return
        if len(r) + len(p) < min_size:
            return
        pivot = max(p | x, key=lambda u: len(nbrs[u] & p))
        for v in list(p - nbrs[pivot]):
            expand(r + [v], p & nbrs[v], x & nbrs[v])
            p.discard(v)
            x.add(v)

    for v in order:
        later = {u for u in nbrs[v] if position[u] > position[v]}
        earlier = {u for u in nbrs[v] if position[u] < position[v]}
        if len(later) + 1 >= min_size:
            expand([v], later, earlier)
    found.sort(key=len, reverse=True)
    out = []
    for c in found[:limit]:
        names = [ctx.name(x) for x in c]
        shown = names if len(names) <= 6 else names[:5]
        text = ctx.text("clique", k=ctx.num(len(c)), names=i18n.join(shown, ctx.lang)
                        + ("" if len(names) <= 6 else ctx.text("and_more", k=ctx.num(len(names) - 5))))
        out.append(Pattern("clique", c, len(c), {"size": len(c)}, text))
    return out


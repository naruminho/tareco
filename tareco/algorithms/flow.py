from collections import deque

from ..errors import TarecoError
from ..graph import _weight_fn

EPS = 1e-12


class Flow:
    """Result of ``max_flow``: the value, how much goes through each edge, and the bottleneck."""

    def __init__(self, value, flows, side, cut):
        self.value = value
        self.flows = flows      # {(u, v): amount}, only edges that carry something
        self.side = side        # nodes still reachable from the source after the flow
        self.cut = cut          # edges that limit the flow, as (u, v, capacity)

    def __repr__(self):
        return f"<Flow value={self.value:g}, {len(self.flows)} edges used, cut of {len(self.cut)} edges>"


def max_flow(g, source, target, capacity="weight"):
    """Most that can go from ``source`` to ``target`` when edges carry at most ``capacity``.

    Dinic's algorithm. Undirected edges carry flow either way. Edges without the
    capacity attribute count as 1. The returned cut is the smallest set of edges
    whose capacities add up to the flow: the bottleneck between the two nodes.
    """
    g._check(source)
    g._check(target)
    if source == target:
        raise TarecoError("source and target must be different nodes")
    cap_of = _weight_fn(capacity)
    nodes = list(g)
    index = {n: i for i, n in enumerate(nodes)}
    head = [[] for _ in nodes]
    to, cap, original = [], [], []
    for u, v, d in g._edge_triples():
        if u == v:
            continue
        c = cap_of(d)
        if c < 0:
            raise TarecoError(f"negative capacity on edge {(u, v)!r}")
        i, j = index[u], index[v]
        head[i].append(len(to)); to.append(j); cap.append(c); original.append((u, v, c))
        head[j].append(len(to)); to.append(i); cap.append(0 if g.directed else c); original.append(None)
    start = list(cap)
    s, t = index[source], index[target]
    total = 0.0

    while True:
        level = [-1] * len(nodes)
        level[s] = 0
        queue = deque([s])
        while queue:
            u = queue.popleft()
            for e in head[u]:
                if cap[e] > EPS and level[to[e]] < 0:
                    level[to[e]] = level[u] + 1
                    queue.append(to[e])
        if level[t] < 0:
            break
        nxt = [0] * len(nodes)
        while True:
            pushed = _augment(s, t, head, to, cap, level, nxt)
            if pushed <= EPS:
                break
            total += pushed

    flows = {}
    for e in range(0, len(to), 2):
        u, v, c = original[e]
        moved = start[e] - cap[e]
        if moved > EPS:
            flows[(u, v)] = moved
        elif moved < -EPS:  # undirected edge used the other way
            flows[(v, u)] = -moved
    reach = {s}
    queue = deque([s])
    while queue:
        u = queue.popleft()
        for e in head[u]:
            if cap[e] > EPS and to[e] not in reach:
                reach.add(to[e])
                queue.append(to[e])
    side = {nodes[i] for i in reach}
    cut = []
    for e in range(0, len(to), 2):
        u, v, c = original[e]
        if (u in side) != (v in side) and (u in side or not g.directed):
            cut.append((u, v, c) if u in side else (v, u, c))
    if isinstance(total, float) and total.is_integer():
        total = int(total)
    return Flow(total, flows, side, cut)


def _augment(s, t, head, to, cap, level, nxt):
    """One augmenting path in the level graph (iterative DFS); returns how much it carried."""
    stack = []
    u = s
    while True:
        if u == t:
            amount = min(cap[e] for e in stack)
            for e in stack:
                cap[e] -= amount
                cap[e ^ 1] += amount
            return amount
        moved = False
        edges = head[u]
        while nxt[u] < len(edges):
            e = edges[nxt[u]]
            v = to[e]
            if cap[e] > EPS and level[v] == level[u] + 1:
                stack.append(e)
                u = v
                moved = True
                break
            nxt[u] += 1
        if moved:
            continue
        if u == s:
            return 0
        level[u] = -1  # dead end for this phase
        e = stack.pop()
        u = to[e ^ 1]
        nxt[u] += 1

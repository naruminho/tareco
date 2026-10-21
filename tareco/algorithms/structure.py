import math
from collections import defaultdict, deque
from heapq import heappop, heappush

from ..errors import HasCycle, TarecoError
from ..graph import _weight_fn
from .centrality import pagerank
from .components import components


def _plain_neighbors(g):
    """Undirected neighbor sets without self-loops."""
    return {u: set(g._all_neighbors(u)) - {u} for u in g}


def triangles(g):
    """Number of triangles each node is part of (direction ignored)."""
    nbrs = _plain_neighbors(g)
    return {u: sum(len(nbrs[u] & nbrs[v]) for v in nbrs[u]) // 2 for u in g}


def clustering(g):
    """Fraction of each node's neighbor pairs that are also connected."""
    nbrs = _plain_neighbors(g)
    tri = triangles(g)
    result = {}
    for u in g:
        d = len(nbrs[u])
        result[u] = 2.0 * tri[u] / (d * (d - 1)) if d > 1 else 0.0
    return result


def transitivity(g):
    """Global clustering: closed triads over all triads."""
    nbrs = _plain_neighbors(g)
    tri = sum(triangles(g).values())
    triads = sum(len(s) * (len(s) - 1) / 2 for s in nbrs.values())
    return tri / triads if triads else 0.0


def density(g):
    n = len(g)
    if n <= 1:
        return 0.0
    possible = n * (n - 1) if g.directed else n * (n - 1) / 2
    return g.edge_count / possible


def core_number(g):
    """Largest ``k`` such that the node belongs to the k-core (direction ignored)."""
    nbrs = _plain_neighbors(g)
    order = {u: i for i, u in enumerate(g)}
    deg = {u: len(s) for u, s in nbrs.items()}
    heap = [(d, order[u], u) for u, d in deg.items()]
    heap.sort(key=lambda t: (t[0], t[1]))
    core = {}
    k = 0
    while heap:
        d, _, u = heappop(heap)
        if u in core or d != deg[u]:
            continue
        k = max(k, d)
        core[u] = k
        for v in nbrs[u]:
            if v not in core:
                deg[v] -= 1
                heappush(heap, (deg[v], order[v], v))
    return {u: core[u] for u in g}


def k_core(g, k=None):
    core = core_number(g)
    if k is None:
        k = max(core.values(), default=0)
    return g.subgraph(u for u, c in core.items() if c >= k)


class _DisjointSet:
    def __init__(self):
        self.parent = {}

    def find(self, x):
        root = self.parent.setdefault(x, x)
        while root != self.parent[root]:
            root = self.parent[root]
        while x != root:
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return False
        self.parent[ra] = rb
        return True


def spanning_tree(g, weight="weight", maximum=False):
    """Minimum (or maximum) spanning forest, as a new undirected graph (Kruskal)."""
    wt = _weight_fn(weight, g)
    edges = sorted(g._edge_triples(), key=lambda e: wt(e[2]), reverse=maximum)
    tree = g._new(False)
    for n, d in g.nodes.items():
        tree._add_node(n, dict(d))
    ds = _DisjointSet()
    for u, v, d in edges:
        if ds.union(u, v):
            tree._add_edge(u, v, dict(d))
    return tree


def topological_sort(g):
    """Order the nodes so every edge points forward. Needs a directed graph with no cycles."""
    if not g.directed:
        raise TarecoError("topological_sort needs a directed graph")
    indeg = {u: len(g._pred[u]) for u in g}
    queue = deque(u for u in g if indeg[u] == 0)
    order = []
    while queue:
        u = queue.popleft()
        order.append(u)
        for v in g._succ[u]:
            indeg[v] -= 1
            if indeg[v] == 0:
                queue.append(v)
    if len(order) < len(g):
        raise HasCycle("the graph has a cycle, so it has no topological order")
    return order


def find_cycle(g):
    """One cycle as a list of nodes (``[a, b, c]`` for a -> b -> c -> a), or None."""
    if g.directed:
        color = {}
        for root in g:
            if root in color:
                continue
            stack = [(root, iter(g._succ[root]))]
            path = [root]
            color[root] = 1
            while stack:
                node, nbrs = stack[-1]
                for v in nbrs:
                    if color.get(v) == 1:
                        return path[path.index(v):]
                    if v not in color:
                        color[v] = 1
                        stack.append((v, iter(g._succ[v])))
                        path.append(v)
                        break
                else:
                    stack.pop()
                    color[path.pop()] = 2
        return None
    parent = {}
    for root in g:
        if root in parent:
            continue
        parent[root] = None
        stack = [root]
        while stack:
            u = stack.pop()
            for v in g._succ[u]:
                if v == u:
                    return [u]
                if v not in parent:
                    parent[v] = u
                    stack.append(v)
                elif parent[u] != v:
                    a, b = [u], [v]
                    while a[-1] is not None:
                        a.append(parent[a[-1]])
                    while b[-1] is not None:
                        b.append(parent[b[-1]])
                    common = next(x for x in a if x in set(b))
                    return a[:a.index(common) + 1] + b[:b.index(common)][::-1]
    return None


def has_cycle(g):
    if g.directed:
        try:
            topological_sort(g)
        except HasCycle:
            return True
        return False
    ds = _DisjointSet()
    return any(not ds.union(u, v) for u, v, _ in g._edge_triples())


def suggest_links(g, node=None, top=10):
    """Missing edges most likely to exist, scored by Adamic-Adar.

    Pairs that share many (and rare) neighbors score higher. Returns
    ``[(u, v, score), ...]``; with ``node`` only pairs involving it.
    """
    nbrs = _plain_neighbors(g)
    order = {u: i for i, u in enumerate(g)}
    scores = defaultdict(float)
    if node is not None:
        g._check(node)
    hubs = nbrs[node] if node is not None else g
    for z in hubs:
        if len(nbrs[z]) < 2:
            continue
        inv = 1.0 / math.log(len(nbrs[z]))
        members = sorted(nbrs[z], key=order.get)
        for i, u in enumerate(members):
            for v in members[i + 1:]:
                if node is not None and node not in (u, v):
                    continue
                if v in nbrs[u]:
                    continue
                scores[(u, v)] += inv
    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], order[kv[0][0]], order[kv[0][1]]))
    return [(u, v, s) for (u, v), s in ranked[:top]]


class Summary(dict):
    def __repr__(self):
        width = max(len(k) for k in self)
        lines = []
        for key, value in self.items():
            if key == "top_nodes":
                value = ", ".join(f"{n!r} ({s:.3f})" for n, s in value)
            elif isinstance(value, float):
                value = f"{value:.4g}"
            lines.append(f"{key.replace('_', ' '):<{width}}  {value}")
        return "\n".join(lines)


def summary(g):
    n = len(g)
    comps = components(g)
    clus = clustering(g)
    pr = pagerank(g) if n else {}
    top = sorted(pr.items(), key=lambda kv: -kv[1])[:5]
    return Summary(
        nodes=n,
        edges=g.edge_count,
        directed=g.directed,
        density=density(g),
        components=len(comps),
        largest_component=len(comps[0]) if comps else 0,
        average_degree=(sum(g.degree().values()) / n) if n else 0.0,
        average_clustering=(sum(clus.values()) / n) if n else 0.0,
        top_nodes=top,
    )

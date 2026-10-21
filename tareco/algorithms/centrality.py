import random
from collections import deque
from heapq import heappop, heappush
from itertools import count

from ..errors import TarecoError
from ..graph import _weight_fn
from .paths import _search


def degree_centrality(g):
    """Fraction of the other nodes each node is connected to."""
    n = len(g)
    if n <= 1:
        return {u: 1.0 for u in g}
    scale = 1.0 / (n - 1)
    return {u: d * scale for u, d in g.degree().items()}


def pagerank(g, alpha=0.85, weight="weight", max_iter=200, tol=1.0e-8):
    """Importance of each node by the random-surfer model. Values sum to 1."""
    nodes = list(g)
    n = len(nodes)
    if n == 0:
        return {}
    wt = _weight_fn(weight)
    out_weight = {u: sum(wt(d) for d in g._succ[u].values()) for u in nodes}
    dangling = [u for u in nodes if out_weight[u] == 0]
    x = dict.fromkeys(nodes, 1.0 / n)
    for _ in range(max_iter):
        last = x
        base = (1.0 - alpha) / n + alpha * sum(last[u] for u in dangling) / n
        x = dict.fromkeys(nodes, base)
        for u in nodes:
            ow = out_weight[u]
            if ow:
                share = alpha * last[u] / ow
                for v, d in g._succ[u].items():
                    x[v] += share * wt(d)
        if sum(abs(x[u] - last[u]) for u in nodes) < n * tol:
            break
    return x


IGRAPH_ABOVE = 1_000  # "auto" hands exact betweenness to igraph above this many nodes


def betweenness(g, normalized=True, weight=None, k=None, seed=0, engine="auto"):
    """How often each node sits on shortest paths between other nodes (Brandes).

    Exact betweenness costs one search per node, which gets slow past a few
    thousand nodes. With ``k`` only ``k`` random sources are used and the result
    is scaled up: a good estimate in a fraction of the time. When the optional
    ``igraph`` package is installed, exact betweenness on big graphs runs there
    (``engine="auto"``); ``engine="python"`` always uses tareco's own code.
    """
    if engine not in ("auto", "python", "igraph"):
        raise TarecoError('engine must be "auto", "python" or "igraph"')
    if k is None and (engine == "igraph" or (engine == "auto" and len(g) > IGRAPH_ABOVE)):
        fast = _igraph_betweenness(g, normalized, weight, required=engine == "igraph")
        if fast is not None:
            return fast
    bc = dict.fromkeys(g, 0.0)
    sources = list(g)
    if k is not None and k < len(sources):
        sources = random.Random(seed).sample(sources, k)
    for s in sources:
        if weight is None:
            order, preds, sigma = _bfs_paths(g, s)
        else:
            order, preds, sigma = _dijkstra_paths(g, s, _weight_fn(weight))
        delta = dict.fromkeys(order, 0.0)
        while order:
            w = order.pop()
            for v in preds[w]:
                delta[v] += sigma[v] / sigma[w] * (1.0 + delta[w])
            if w != s:
                bc[w] += delta[w]
    n = len(g)
    if normalized:
        scale = 1.0 / ((n - 1) * (n - 2)) if n > 2 else None
    else:
        scale = None if g.directed else 0.5
    if len(sources) < n:
        scale = (scale or 1.0) * n / len(sources)
    if scale is not None:
        for v in bc:
            bc[v] *= scale
    return bc


def _igraph_betweenness(g, normalized, weight, required):
    try:
        import igraph
    except ImportError:
        if required:
            raise TarecoError('engine="igraph" needs the igraph package: pip install igraph') from None
        return None
    nodes = list(g)
    index = {n: i for i, n in enumerate(nodes)}
    triples = [(u, v, d) for u, v, d in g._edge_triples() if u != v]
    ig = igraph.Graph(n=len(nodes), edges=[(index[u], index[v]) for u, v, _ in triples],
                      directed=g.directed)
    weights = None
    if weight is not None:
        wt = _weight_fn(weight)
        weights = [wt(d) for _, _, d in triples]
    raw = ig.betweenness(directed=g.directed, weights=weights)
    n = len(nodes)
    if normalized:
        # igraph counts each unordered pair once in undirected graphs; tareco counts both ways
        scale = (1.0 if g.directed else 2.0) / ((n - 1) * (n - 2)) if n > 2 else 1.0
    else:
        scale = 1.0
    return {node: raw[i] * scale for node, i in index.items()}


def _bfs_paths(g, s):
    order = []
    preds = {s: []}
    sigma = {s: 1.0}
    dist = {s: 0}
    queue = deque([s])
    while queue:
        v = queue.popleft()
        order.append(v)
        for w in g._succ[v]:
            if w not in dist:
                dist[w] = dist[v] + 1
                sigma[w] = 0.0
                preds[w] = []
                queue.append(w)
            if dist[w] == dist[v] + 1:
                sigma[w] += sigma[v]
                preds[w].append(v)
    return order, preds, sigma


def _dijkstra_paths(g, s, wt):
    order = []
    preds = {s: []}
    sigma = {s: 1.0}
    done = {}
    seen = {s: 0}
    tie = count()
    heap = [(0, next(tie), s, s)]
    while heap:
        d, _, pred, v = heappop(heap)
        if v in done:
            continue
        if v != s:
            sigma[v] += sigma[pred]
        order.append(v)
        done[v] = d
        for w, attrs in g._succ[v].items():
            nd = d + wt(attrs)
            if w in done:
                continue
            if w not in seen or nd < seen[w]:
                seen[w] = nd
                heappush(heap, (nd, next(tie), v, w))
                sigma[w] = 0.0
                preds[w] = [v]
            elif nd == seen[w]:
                sigma[w] += sigma[v]
                preds[w].append(v)
    return order, preds, sigma


def closeness(g, weight=None):
    """How near each node is to the nodes it can reach (Wasserman-Faust scaling)."""
    n = len(g)
    result = {}
    for u in g:
        dist, _ = _search(g, u, weight)
        total = sum(dist.values())
        reach = len(dist) - 1
        if total > 0 and n > 1:
            result[u] = (reach / total) * (reach / (n - 1))
        else:
            result[u] = 0.0
    return result

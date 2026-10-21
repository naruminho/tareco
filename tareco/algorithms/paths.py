from collections import deque
from heapq import heappop, heappush
from itertools import count

from ..errors import NoPath, NotConnected, TarecoError
from ..graph import _weight_fn


def bfs(g, source):
    """Nodes in breadth-first order from ``source``."""
    g._check(source)
    seen = {source}
    queue = deque([source])
    order = []
    while queue:
        u = queue.popleft()
        order.append(u)
        for v in g._succ[u]:
            if v not in seen:
                seen.add(v)
                queue.append(v)
    return order


def dfs(g, source):
    """Nodes in depth-first (preorder) order from ``source``."""
    g._check(source)
    seen = set()
    stack = [source]
    order = []
    while stack:
        u = stack.pop()
        if u in seen:
            continue
        seen.add(u)
        order.append(u)
        stack.extend(v for v in reversed(list(g._succ[u])) if v not in seen)
    return order


def _search(g, source, weight, target=None):
    """Single-source search: ``(dist, parent)``. BFS without weight, Dijkstra with it."""
    g._check(source)
    dist = {source: 0}
    parent = {source: None}
    if weight is None:
        queue = deque([source])
        while queue:
            u = queue.popleft()
            if u == target:
                break
            for v in g._succ[u]:
                if v not in dist:
                    dist[v] = dist[u] + 1
                    parent[v] = u
                    queue.append(v)
        return dist, parent

    wt = _weight_fn(weight, g)
    done = {}
    tie = count()
    heap = [(0, next(tie), source)]
    while heap:
        d, _, u = heappop(heap)
        if u in done:
            continue
        done[u] = d
        if u == target:
            break
        for v, attrs in g._succ[u].items():
            w = wt(attrs)
            if w < 0:
                raise TarecoError(f"negative weight on edge {(u, v)!r}; shortest paths need weights >= 0")
            nd = d + w
            if v not in done and (v not in dist or nd < dist[v]):
                dist[v] = nd
                parent[v] = u
                heappush(heap, (nd, next(tie), v))
    return done, parent


def shortest_path(g, source, target, weight=None):
    g._check(target)
    dist, parent = _search(g, source, weight, target)
    if target not in dist:
        raise NoPath(f"no path from {source!r} to {target!r}")
    path = [target]
    while path[-1] != source:
        path.append(parent[path[-1]])
    path.reverse()
    return path


def distance(g, source, target, weight=None):
    g._check(target)
    dist, _ = _search(g, source, weight, target)
    if target not in dist:
        raise NoPath(f"no path from {source!r} to {target!r}")
    return dist[target]


def distances(g, source, weight=None):
    return dict(_search(g, source, weight)[0])


def eccentricity(g):
    """Largest distance (in steps) from each node. Needs a (strongly) connected graph."""
    n = len(g)
    result = {}
    for u in g:
        dist, _ = _search(g, u, None)
        if len(dist) < n:
            raise NotConnected("the graph is not connected, so distances can be infinite")
        result[u] = max(dist.values())
    return result


def diameter(g):
    if len(g) == 0:
        raise TarecoError("the graph is empty")
    return max(eccentricity(g).values())


def _restricted_path(g, source, target, weight, banned_nodes, banned_edges):
    """Shortest path avoiding some nodes and edges; ``None`` when there is none."""
    wt = _weight_fn(weight, g)
    dist = {source: 0}
    parent = {source: None}
    tie = count()
    heap = [(0, next(tie), source)]
    done = set()
    while heap:
        d, _, u = heappop(heap)
        if u in done:
            continue
        done.add(u)
        if u == target:
            path = [target]
            while path[-1] != source:
                path.append(parent[path[-1]])
            path.reverse()
            return d, path
        for v, attrs in g._succ[u].items():
            if v in banned_nodes or (u, v) in banned_edges or v in done:
                continue
            nd = d + (wt(attrs) if weight is not None else 1)
            if v not in dist or nd < dist[v]:
                dist[v] = nd
                parent[v] = u
                heappush(heap, (nd, next(tie), v))
    return None


def _path_cost(g, path, weight):
    if weight is None:
        return len(path) - 1
    wt = _weight_fn(weight, g)
    return sum(wt(g._succ[a][b]) for a, b in zip(path, path[1:]))


def k_shortest_paths(g, source, target, k=3, weight=None):
    """Up to ``k`` loopless paths from ``source`` to ``target``, shortest first (Yen).

    Handy when the best route is not enough: the alternatives show how much two
    nodes depend on a single path.
    """
    g._check(source)
    g._check(target)
    first = _restricted_path(g, source, target, weight, set(), set())
    if first is None:
        raise NoPath(f"no path from {source!r} to {target!r}")
    found = [first[1]]
    seen = {tuple(first[1])}
    candidates = []
    tie = count()
    while len(found) < k:
        last = found[-1]
        for j in range(len(last) - 1):
            spur = last[j]
            root = last[:j + 1]
            banned_edges = set()
            for p in found:
                if len(p) > j and p[:j + 1] == root:
                    banned_edges.add((p[j], p[j + 1]))
                    if not g.directed:
                        banned_edges.add((p[j + 1], p[j]))
            spur_path = _restricted_path(g, spur, target, weight, set(root[:-1]), banned_edges)
            if spur_path is None:
                continue
            path = root[:-1] + spur_path[1]
            key = tuple(path)
            if key not in seen:
                seen.add(key)
                heappush(candidates, (_path_cost(g, path, weight), next(tie), path))
        if not candidates:
            break
        found.append(heappop(candidates)[2])
    return found

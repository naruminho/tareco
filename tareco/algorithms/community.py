import random
from collections import defaultdict, deque

from ..errors import TarecoError
from ..graph import _weight_fn


def _undirected_weights(g, weight):
    """Integer-indexed symmetric adjacency. Self-loop weight sits at ``adj[i][i]``."""
    nodes = list(g)
    index = {n: i for i, n in enumerate(nodes)}
    adj = [defaultdict(float) for _ in nodes]
    wt = _weight_fn(weight, g)
    for u, v, d in g._edge_triples():
        w = float(wt(d))
        i, j = index[u], index[v]
        if i == j:
            adj[i][i] += w
        else:
            adj[i][j] += w
            adj[j][i] += w
    return nodes, adj


def _degrees(adj):
    return [sum(w for j, w in row.items() if j != i) + 2 * row.get(i, 0.0) for i, row in enumerate(adj)]


def louvain(g, weight="weight", resolution=1.0, seed=0):
    """Communities by the Louvain method, as a list of sets (biggest first).

    Directed graphs are treated as undirected. ``seed`` fixes the visiting
    order so results are repeatable; pass ``None`` for a random one.
    """
    nodes, adj = _undirected_weights(g, weight)
    if not nodes:
        return []
    rng = random.Random(seed)
    groups = [[n] for n in nodes]
    while True:
        k = _degrees(adj)
        two_m = sum(k)
        if two_m == 0:
            break
        comm, moved = _local_moves(adj, k, two_m, resolution, rng)
        if not moved:
            break
        labels = {c: i for i, c in enumerate(dict.fromkeys(comm))}
        new_groups = [[] for _ in labels]
        for i, members in enumerate(groups):
            new_groups[labels[comm[i]]].extend(members)
        new_adj = [defaultdict(float) for _ in labels]
        for i, row in enumerate(adj):
            ci = labels[comm[i]]
            for j, w in row.items():
                cj = labels[comm[j]]
                if i == j:
                    new_adj[ci][ci] += w
                elif ci == cj:
                    new_adj[ci][ci] += w / 2
                else:
                    new_adj[ci][cj] += w
        groups, adj = new_groups, new_adj
    return sorted((set(m) for m in groups), key=len, reverse=True)


def _local_moves(adj, k, two_m, resolution, rng):
    # Fast local moving: after a node moves, only its neighbors outside the new
    # community can gain from moving, so only they go back in the queue.
    n = len(adj)
    comm = list(range(n))
    total = list(k)
    order = list(range(n))
    rng.shuffle(order)
    queue = deque(order)
    queued = [True] * n
    moved_any = False
    while queue:
        i = queue.popleft()
        queued[i] = False
        ci = comm[i]
        links = {}
        for j, w in adj[i].items():
            if j != i:
                c = comm[j]
                links[c] = links.get(c, 0.0) + w
        ki = k[i]
        total[ci] -= ki
        factor = resolution * ki / two_m
        best, best_gain = ci, links.get(ci, 0.0) - factor * total[ci]
        for c, w in links.items():
            gain = w - factor * total[c]
            if gain > best_gain + 1e-12:
                best, best_gain = c, gain
        total[best] += ki
        if best != ci:
            comm[i] = best
            moved_any = True
            for j in adj[i]:
                if not queued[j] and j != i and comm[j] != best:
                    queued[j] = True
                    queue.append(j)
    return comm, moved_any


def modularity(g, communities, weight="weight", resolution=1.0):
    """Quality of a split into communities, from about -0.5 to 1 (higher is better)."""
    nodes, adj = _undirected_weights(g, weight)
    index = {n: i for i, n in enumerate(nodes)}
    label = {}
    for c, members in enumerate(communities):
        for n in members:
            if n not in index:
                raise TarecoError(f"node {n!r} is not in the graph")
            if index[n] in label:
                raise TarecoError(f"node {n!r} is in more than one community")
            label[index[n]] = c
    if len(label) != len(nodes):
        raise TarecoError("every node must be in exactly one community")
    k = _degrees(adj)
    two_m = sum(k)
    if two_m == 0:
        return 0.0
    inside = defaultdict(float)
    degree_sum = defaultdict(float)
    for i, row in enumerate(adj):
        degree_sum[label[i]] += k[i]
        for j, w in row.items():
            if label[i] == label[j]:
                inside[label[i]] += w if i == j else w / 2
    m = two_m / 2
    return sum(inside[c] / m - resolution * (degree_sum[c] / two_m) ** 2 for c in degree_sum)

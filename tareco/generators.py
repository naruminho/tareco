"""Ready-made graphs, for experiments and demos."""

import random

from .errors import TarecoError
from .graph import Graph


def complete_graph(n, directed=False):
    g = Graph(directed=directed)
    g.add_nodes(range(n))
    for u in range(n):
        for v in range(n):
            if u != v and (directed or u < v):
                g.add_edge(u, v)
    return g


def path_graph(n, directed=False):
    g = Graph(directed=directed)
    g.add_nodes(range(n))
    g.add_edges((i, i + 1) for i in range(n - 1))
    return g


def cycle_graph(n, directed=False):
    g = path_graph(n, directed)
    if n > 2:
        g.add_edge(n - 1, 0)
    return g


def star_graph(n):
    """A center ``0`` linked to ``n`` leaves."""
    g = Graph()
    g.add_node(0)
    g.add_edges((0, i) for i in range(1, n + 1))
    return g


def grid_graph(rows, cols):
    """A lattice; nodes are ``(row, col)`` tuples."""
    g = Graph()
    for r in range(rows):
        for c in range(cols):
            g.add_node((r, c))
            if r:
                g.add_edge((r - 1, c), (r, c))
            if c:
                g.add_edge((r, c - 1), (r, c))
    return g


def random_graph(n, p, directed=False, seed=None):
    """Erdős–Rényi: every possible edge exists with probability ``p``."""
    rng = random.Random(seed)
    g = Graph(directed=directed)
    g.add_nodes(range(n))
    for u in range(n):
        for v in range(n) if directed else range(u + 1, n):
            if u != v and rng.random() < p:
                g.add_edge(u, v)
    return g


def scale_free_graph(n, m=2, seed=None):
    """Barabási–Albert: new nodes prefer to link to popular ones (a few big hubs)."""
    if not 1 <= m < n:
        raise TarecoError("scale_free_graph needs 1 <= m < n")
    rng = random.Random(seed)
    g = Graph()
    g.add_nodes(range(m))
    targets = list(range(m))
    pool = []
    for new in range(m, n):
        for t in set(targets):
            g.add_edge(new, t)
        pool.extend(targets)
        pool.extend([new] * m)
        chosen = set()
        while len(chosen) < m:
            chosen.add(rng.choice(pool))
        targets = list(chosen)
    return g


def small_world_graph(n, k=4, p=0.1, seed=None):
    """Watts–Strogatz: a ring where each node knows ``k`` neighbors, with a few random shortcuts."""
    if k >= n or k < 2:
        raise TarecoError("small_world_graph needs 2 <= k < n")
    rng = random.Random(seed)
    g = Graph()
    g.add_nodes(range(n))
    for u in range(n):
        for j in range(1, k // 2 + 1):
            g.add_edge(u, (u + j) % n)
    for j in range(1, k // 2 + 1):
        for u in range(n):
            v = (u + j) % n
            if rng.random() < p and g.has_edge(u, v):
                choices = [w for w in range(n) if w != u and not g.has_edge(u, w)]
                if choices:
                    g.remove_edge(u, v)
                    g.add_edge(u, rng.choice(choices))
    return g


def community_graph(sizes, p_in=0.3, p_out=0.01, seed=None):
    """Planted groups: dense inside each group, sparse between them.

    Each node gets a ``group`` attribute, handy to compare with ``communities()``.
    """
    rng = random.Random(seed)
    g = Graph()
    group_of = []
    for gi, size in enumerate(sizes):
        group_of.extend([gi] * size)
    for u, gu in enumerate(group_of):
        g.add_node(u, group=gu)
    for u in range(len(group_of)):
        for v in range(u + 1, len(group_of)):
            p = p_in if group_of[u] == group_of[v] else p_out
            if rng.random() < p:
                g.add_edge(u, v)
    return g

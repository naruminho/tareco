from .errors import EdgeNotFound, NodeNotFound, TarecoError


class NodeView:
    """Read-only view of the nodes. Iterate for ids, index for attributes."""

    __slots__ = ("_g",)

    def __init__(self, graph):
        self._g = graph

    def __iter__(self):
        return iter(self._g._nodes)

    def __len__(self):
        return len(self._g._nodes)

    def __contains__(self, node):
        return node in self._g

    def __getitem__(self, node):
        try:
            return self._g._nodes[node]
        except (KeyError, TypeError):
            raise NodeNotFound(f"node {node!r} is not in the graph") from None

    def items(self):
        """Pairs of ``(node, attributes)``."""
        return self._g._nodes.items()

    def __repr__(self):
        return f"NodeView({_preview(list(self))})"


class EdgeView:
    """Read-only view of the edges. Iterate for ``(u, v)``, index with ``[u, v]``."""

    __slots__ = ("_g",)

    def __init__(self, graph):
        self._g = graph

    def __iter__(self):
        for u, v, _ in self._g._edge_triples():
            yield u, v

    def __len__(self):
        return self._g._edge_count

    def __contains__(self, edge):
        try:
            u, v = edge
        except (TypeError, ValueError):
            return False
        return self._g.has_edge(u, v)

    def __getitem__(self, edge):
        u, v = edge
        try:
            return self._g._succ[u][v]
        except (KeyError, TypeError):
            raise EdgeNotFound(f"edge {edge!r} is not in the graph") from None

    def items(self):
        """Pairs of ``((u, v), attributes)``."""
        for u, v, d in self._g._edge_triples():
            yield (u, v), d

    def __repr__(self):
        return f"EdgeView({_preview(list(self))})"


def _preview(items, limit=10):
    shown = ", ".join(repr(i) for i in items[:limit])
    return f"[{shown}, ...]" if len(items) > limit else f"[{shown}]"


class Graph:
    """A graph with attributes on nodes and edges.

    ``data`` can be almost anything with edges in it: a list of pairs, a dict of
    neighbors, a CSV/JSON path, a pandas, polars or Spark DataFrame, a networkx
    graph or another Graph. ``nodes`` adds node attributes from the same kinds
    of sources. Spark DataFrames are streamed to the driver and refused above
    ``max_rows`` rows (aggregate them in Spark first, or pass ``max_rows=None``).

    >>> g = Graph([("ana", "bia"), ("bia", "caio", 2.5)])
    >>> g.shortest_path("ana", "caio")
    ['ana', 'bia', 'caio']
    """

    def __init__(self, data=None, *, directed=None, nodes=None, source=None,
                 target=None, node_id=None, max_rows=1_000_000, **attrs):
        self.attrs = dict(attrs)
        self._reset(bool(directed))
        if data is not None or nodes is not None:
            from .io import load_into
            load_into(self, data, directed=directed, nodes=nodes, source=source,
                      target=target, node_id=node_id, max_rows=max_rows)

    def _new(self, directed):
        g = Graph(directed=directed)
        g.attrs = dict(self.attrs)
        return g

    def _reset(self, directed):
        self.directed = directed
        self._nodes = {}
        self._succ = {}
        self._pred = {} if directed else self._succ
        self._edge_count = 0

    # ---------------------------------------------------------------- building

    def add_node(self, node, **attrs):
        """Add ``node`` (or update its attributes if it already exists)."""
        self._add_node(node, attrs)

    def _add_node(self, node, attrs):
        if node is None:
            raise TarecoError("None cannot be a node")
        d = self._nodes.get(node)
        if d is None:
            d = self._nodes[node] = {}
            self._succ[node] = {}
            if self.directed:
                self._pred[node] = {}
        d.update(attrs)

    def add_nodes(self, nodes):
        """Add many nodes: plain ids or ``(id, {attributes})`` pairs."""
        for item in nodes:
            if isinstance(item, tuple) and len(item) == 2 and isinstance(item[1], dict):
                self._add_node(item[0], item[1])
            else:
                self._add_node(item, {})

    def add_edge(self, u, v, **attrs):
        """Add an edge ``u -> v`` (or update its attributes). Missing nodes are created."""
        self._add_edge(u, v, attrs)

    def _add_edge(self, u, v, attrs):
        if u not in self._nodes:
            self._add_node(u, {})
        if v not in self._nodes:
            self._add_node(v, {})
        d = self._succ[u].get(v)
        if d is None:
            d = self._succ[u][v] = {}
            if self.directed:
                self._pred[v][u] = d
            else:
                self._succ[v][u] = d
            self._edge_count += 1
        d.update(attrs)

    def add_edges(self, edges):
        """Add many edges: ``(u, v)``, ``(u, v, weight)`` or ``(u, v, {attributes})``."""
        for e in edges:
            if len(e) == 2:
                self._add_edge(e[0], e[1], {})
            elif len(e) == 3:
                extra = e[2]
                self._add_edge(e[0], e[1], dict(extra) if isinstance(extra, dict) else {"weight": extra})
            else:
                raise TarecoError(f"cannot read edge {e!r}: use (u, v), (u, v, weight) or (u, v, {{attributes}})")

    def remove_node(self, node):
        """Remove ``node`` and every edge touching it."""
        self._check(node)
        for v in list(self._succ[node]):
            self.remove_edge(node, v)
        if self.directed:
            for u in list(self._pred[node]):
                self.remove_edge(u, node)
            del self._pred[node]
        del self._succ[node]
        del self._nodes[node]

    def remove_edge(self, u, v):
        try:
            del self._succ[u][v]
        except (KeyError, TypeError):
            raise EdgeNotFound(f"edge {(u, v)!r} is not in the graph") from None
        if self.directed:
            del self._pred[v][u]
        elif u != v:
            del self._succ[v][u]
        self._edge_count -= 1

    # ----------------------------------------------------------------- queries

    @property
    def nodes(self):
        return NodeView(self)

    @property
    def edges(self):
        return EdgeView(self)

    @property
    def node_count(self):
        return len(self._nodes)

    @property
    def edge_count(self):
        return self._edge_count

    def __len__(self):
        return len(self._nodes)

    def __iter__(self):
        return iter(self._nodes)

    def __contains__(self, node):
        try:
            return node in self._nodes
        except TypeError:
            return False

    def has_node(self, node):
        return node in self

    def has_edge(self, u, v):
        try:
            return v in self._succ[u]
        except (KeyError, TypeError):
            return False

    def neighbors(self, node):
        """Nodes reachable in one step (successors, for directed graphs)."""
        self._check(node)
        return list(self._succ[node])

    def successors(self, node):
        self._check(node)
        return list(self._succ[node])

    def predecessors(self, node):
        self._check(node)
        return list(self._pred[node])

    def degree(self, node=None, weight=None):
        """Degree of ``node``, or a dict with every node's degree.

        With ``weight`` (an edge attribute name) the degree is the sum of the
        weights. Self-loops count twice in undirected graphs.
        """
        return self._per_node(node, lambda n: self._degree_of(n, weight, "all"))

    def in_degree(self, node=None, weight=None):
        return self._per_node(node, lambda n: self._degree_of(n, weight, "in"))

    def out_degree(self, node=None, weight=None):
        return self._per_node(node, lambda n: self._degree_of(n, weight, "out"))

    def _degree_of(self, n, weight, mode):
        wt = _weight_fn(weight)
        out = sum(wt(d) for d in self._succ[n].values())
        if not self.directed:
            if n in self._succ[n]:
                out += wt(self._succ[n][n])
            return out
        if mode == "out":
            return out
        inn = sum(wt(d) for d in self._pred[n].values())
        return inn if mode == "in" else out + inn

    def _per_node(self, node, fn):
        if node is None:
            return {n: fn(n) for n in self._nodes}
        self._check(node)
        return fn(node)

    def _check(self, node):
        if node not in self:
            raise NodeNotFound(f"node {node!r} is not in the graph")

    def _edge_triples(self):
        if self.directed:
            for u, nbrs in self._succ.items():
                for v, d in nbrs.items():
                    yield u, v, d
        else:
            seen = set()
            for u, nbrs in self._succ.items():
                for v, d in nbrs.items():
                    if v not in seen:
                        yield u, v, d
                seen.add(u)

    def _all_neighbors(self, node):
        """Neighbors ignoring direction."""
        if not self.directed:
            return self._succ[node].keys()
        return self._succ[node].keys() | self._pred[node].keys()

    # -------------------------------------------------------------- transforms

    def copy(self):
        g = self._new(self.directed)
        for n, d in self._nodes.items():
            g._add_node(n, dict(d))
        for u, v, d in self._edge_triples():
            g._add_edge(u, v, dict(d))
        return g

    def subgraph(self, nodes):
        """A new graph with only ``nodes`` and the edges between them."""
        keep = [n for n in dict.fromkeys(nodes) if n in self]
        keep_set = set(keep)
        g = self._new(self.directed)
        for n in keep:
            g._add_node(n, dict(self._nodes[n]))
        for u, v, d in self._edge_triples():
            if u in keep_set and v in keep_set:
                g._add_edge(u, v, dict(d))
        return g

    def ego(self, node, radius=1):
        """The neighborhood of ``node`` up to ``radius`` steps (ignoring direction)."""
        self._check(node)
        seen = {node}
        frontier = [node]
        for _ in range(radius):
            nxt = []
            for u in frontier:
                for v in self._all_neighbors(u):
                    if v not in seen:
                        seen.add(v)
                        nxt.append(v)
            frontier = nxt
        return self.subgraph(n for n in self._nodes if n in seen)

    def reverse(self):
        """Copy with every edge flipped (a plain copy for undirected graphs)."""
        if not self.directed:
            return self.copy()
        g = self._new(True)
        for n, d in self._nodes.items():
            g._add_node(n, dict(d))
        for u, v, d in self._edge_triples():
            g._add_edge(v, u, dict(d))
        return g

    def to_undirected(self):
        g = self._new(False)
        for n, d in self._nodes.items():
            g._add_node(n, dict(d))
        for u, v, d in self._edge_triples():
            g._add_edge(u, v, dict(d))
        return g

    def to_directed(self):
        """Directed copy; each undirected edge becomes two opposite edges."""
        g = self._new(True)
        for n, d in self._nodes.items():
            g._add_node(n, dict(d))
        for u, v, d in self._edge_triples():
            g._add_edge(u, v, dict(d))
            if not self.directed:
                g._add_edge(v, u, dict(d))
        return g

    # -------------------------------------------------------------- algorithms

    def shortest_path(self, source, target, weight=None):
        """List of nodes from ``source`` to ``target``. ``weight`` names an edge attribute."""
        from .algorithms.paths import shortest_path
        return shortest_path(self, source, target, weight)

    def distance(self, source, target, weight=None):
        """Number of steps (or sum of weights) of the shortest path."""
        from .algorithms.paths import distance
        return distance(self, source, target, weight)

    def distances(self, source, weight=None):
        """Distance from ``source`` to every node it can reach."""
        from .algorithms.paths import distances
        return distances(self, source, weight)

    def diameter(self):
        """Longest shortest path, in steps."""
        from .algorithms.paths import diameter
        return diameter(self)

    def pagerank(self, alpha=0.85, weight="weight"):
        from .algorithms.centrality import pagerank
        return pagerank(self, alpha=alpha, weight=weight)

    def betweenness(self, normalized=True, weight=None, k=None, seed=0, engine="auto"):
        """Bridge score of each node. Pass ``k`` (e.g. 500) to estimate it fast on big graphs."""
        from .algorithms.centrality import betweenness
        return betweenness(self, normalized=normalized, weight=weight, k=k, seed=seed, engine=engine)

    def max_flow(self, source, target, capacity="weight"):
        """How much can go from ``source`` to ``target``, and the bottleneck edges (min cut)."""
        from .algorithms.flow import max_flow
        return max_flow(self, source, target, capacity=capacity)

    def k_shortest_paths(self, source, target, k=3, weight=None):
        """The ``k`` best loopless routes between two nodes, shortest first."""
        from .algorithms.paths import k_shortest_paths
        return k_shortest_paths(self, source, target, k=k, weight=weight)

    def closeness(self, weight=None):
        from .algorithms.centrality import closeness
        return closeness(self, weight=weight)

    def degree_centrality(self):
        from .algorithms.centrality import degree_centrality
        return degree_centrality(self)

    def communities(self, weight="weight", resolution=1.0, seed=0):
        """Groups of densely connected nodes (Louvain), biggest first."""
        from .algorithms.community import louvain
        return louvain(self, weight=weight, resolution=resolution, seed=seed)

    def modularity(self, communities, weight="weight", resolution=1.0):
        from .algorithms.community import modularity
        return modularity(self, communities, weight=weight, resolution=resolution)

    def components(self):
        """Connected components (weakly connected, for directed graphs), biggest first."""
        from .algorithms.components import components
        return components(self)

    def strong_components(self):
        from .algorithms.components import strong_components
        return strong_components(self)

    def is_connected(self):
        from .algorithms.components import is_connected
        return is_connected(self)

    def clustering(self, node=None):
        from .algorithms.structure import clustering
        values = clustering(self)
        if node is None:
            return values
        self._check(node)
        return values[node]

    def triangles(self, node=None):
        from .algorithms.structure import triangles
        values = triangles(self)
        if node is None:
            return values
        self._check(node)
        return values[node]

    def core_number(self):
        from .algorithms.structure import core_number
        return core_number(self)

    def k_core(self, k=None):
        """Subgraph where every node has at least ``k`` neighbors (default: the innermost core)."""
        from .algorithms.structure import k_core
        return k_core(self, k)

    def spanning_tree(self, weight="weight", maximum=False):
        from .algorithms.structure import spanning_tree
        return spanning_tree(self, weight=weight, maximum=maximum)

    def topological_sort(self):
        from .algorithms.structure import topological_sort
        return topological_sort(self)

    def has_cycle(self):
        from .algorithms.structure import has_cycle
        return has_cycle(self)

    def suggest_links(self, node=None, top=10):
        """Likely missing edges as ``(u, v, score)``, best first (Adamic-Adar)."""
        from .algorithms.structure import suggest_links
        return suggest_links(self, node, top)

    def transitivity(self):
        from .algorithms.structure import transitivity
        return transitivity(self)

    def bfs(self, source):
        from .algorithms.paths import bfs
        return bfs(self, source)

    def dfs(self, source):
        from .algorithms.paths import dfs
        return dfs(self, source)

    def density(self):
        from .algorithms.structure import density
        return density(self)

    def explain(self, groups=None, lang=None, top=5, label=None, weight="weight"):
        """The main facts about the network, in plain language ("en" or "pt").

        Groups, what characterizes each one, the most important nodes, bridges
        between groups, hubs, one-way flows and where the weight concentrates.
        """
        from .insights import explain
        return explain(self, groups=groups, lang=lang, top=top, label=label, weight=weight)

    def profile(self, groups=None, attrs=None, top=3, lang=None, label=None):
        """What characterizes each group (communities by default) compared with the whole network."""
        from .insights import profile
        return profile(self, groups=groups, attrs=attrs, top=top, lang=lang, label=label)

    def project(self, nodes, method="count", min_shared=1, max_item_size=1000):
        """Treat the graph as two-sided and link ``nodes`` that share neighbors.

        ``nodes`` is the side to keep (an iterable, or a predicate on
        ``(node, attrs)``). See ``tareco.project`` for the methods.
        """
        from .bipartite import project_graph
        return project_graph(self, nodes, method=method, min_shared=min_shared,
                             max_item_size=max_item_size)

    def patterns(self, kinds=None, lang=None, limit=10, weight="weight", max_cycle=4, label=None,
                 min_fan=5):
        """Shapes worth a look: loops, fan-ins and fan-outs, relays, chains, stars, cliques.

        Each pattern has ``kind``, ``nodes``, ``score`` and a plain-language ``text``.
        Loops, fans, relays and chains need a directed graph.
        """
        from .patterns import find_patterns
        return find_patterns(self, kinds=kinds, lang=lang, limit=limit, weight=weight,
                             max_cycle=max_cycle, label=label, min_fan=min_fan)

    def summary(self):
        """Headline numbers about the graph."""
        from .algorithms.structure import summary
        return summary(self)

    # ------------------------------------------------------------------ output

    def show(self, **options):
        """Open the interactive view (inline in notebooks, in the browser otherwise)."""
        from .viz import show
        show(self, **options)

    def save(self, path, **options):
        """Write the interactive view to a standalone HTML file."""
        from .viz import save
        return save(self, path, **options)

    def report(self, path=None, title=None, lang=None, label=None, **view):
        """A single HTML file with the findings, group and node tables, and the graph.

        Made to be sent to someone. Returns the path, or the HTML when ``path`` is None.
        """
        from .report import report
        return report(self, path, title=title, lang=lang, label=label, **view)

    def to_html(self, **options):
        from .viz import to_html
        return to_html(self, **options)

    def _repr_html_(self):
        # big graphs are trimmed by the view itself; past this, rendering would be a surprise
        if not self._nodes or len(self._nodes) > 200_000:
            return None
        from .viz import notebook_html
        return notebook_html(self)

    def to_dict(self):
        from .io import to_dict
        return to_dict(self)

    def to_json(self, path=None, indent=2):
        from .io import to_json
        return to_json(self, path, indent)

    def to_csv(self, edges_path, nodes_path=None):
        from .io import to_csv
        to_csv(self, edges_path, nodes_path)

    def to_pandas(self, metrics=None):
        """``(nodes, edges)`` as two pandas DataFrames.

        ``metrics`` adds node columns: any of "degree", "in_degree",
        "out_degree", "pagerank", "betweenness", "closeness", "clustering",
        "core", "community", "component".
        """
        from .io import to_pandas
        return to_pandas(self, metrics)

    def to_spark(self, spark, metrics=None):
        """``(nodes, edges)`` as Spark DataFrames (same ``metrics`` as ``to_pandas``)."""
        from .metrics import to_spark
        return to_spark(self, spark, metrics)

    def to_networkx(self):
        from .io import to_networkx
        return to_networkx(self)

    def __repr__(self):
        kind = "directed" if self.directed else "undirected"
        return f"<Graph {kind}, {self.node_count} nodes, {self.edge_count} edges>"


def _weight_fn(weight):
    """``attrs -> number`` for an edge attribute name; missing values count as 1."""
    if weight is None:
        return lambda d: 1
    return lambda d: d.get(weight, 1)

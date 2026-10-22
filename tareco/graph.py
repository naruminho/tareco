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

    ``weight`` names the column that says how strong each connection is (an
    amount, a count). Without it, a numeric column called weight, amount,
    value, quantity, total (or peso, valor, quantidade...) is used, or else the
    only number column. Every algorithm and the view then use it by default.

    Tables can say more:

    kind          what these links are ("transfer"); tables of other kinds join
                  with ``add_links``.
    keep          True (or a list of columns) keeps the rows behind each link, for
                  ``rows()`` and for looking at single transfers.
    account, counterparty, amount
                  read a bank statement: one row per entry, money out negative.
    source_kind, target_kind
                  the kinds of node at each end ("account", "device").
    skip          ids to leave out, with every row that has them ("N/A", "UNKNOWN").
                  Placeholders that tie many rows together come with a warning.

    >>> g = Graph([("ana", "bia"), ("bia", "caio", 2.5)])
    >>> g.shortest_path("ana", "caio")
    ['ana', 'bia', 'caio']
    """

    def __init__(self, data=None, *, directed=None, nodes=None, source=None,
                 target=None, node_id=None, weight=None, max_rows=1_000_000, kind=None, keep=None,
                 account=None, counterparty=None, amount=None, source_kind=None, target_kind=None,
                 skip=None, **attrs):
        self.attrs = dict(attrs)
        self._reset(bool(directed))
        if data is not None or nodes is not None:
            from .io import load_into
            load_into(self, data, directed=directed, nodes=nodes, source=source,
                      target=target, node_id=node_id, max_rows=max_rows, kind=kind, keep=keep,
                      account=account, counterparty=counterparty, amount=amount,
                      source_kind=source_kind, target_kind=target_kind, skip=skip)
        from .io import choose_weight
        choose_weight(self, weight)

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
        self._events = []  # (u, v, kind, row): the rows behind the links, when kept
        self._memo = None  # results shared inside one explain(), review(), view...

    def _memoized(self):
        """While inside, heavy results (PageRank, groups, patterns, the kept rows) are worked
        out once and shared; they are dropped on the way out, so they never go stale."""
        import gc
        from contextlib import contextmanager

        @contextmanager
        def scope():
            if self._memo is not None:
                yield
                return
            self._memo = {}
            collecting = gc.isenabled()
            gc.disable()  # millions of objects stay alive in here; the collector would walk them over and over
            try:
                yield
            finally:
                self._memo = None
                if collecting:
                    gc.enable()
        return scope()

    def _cached(self, key, compute):
        memo = getattr(self, "_memo", None)
        if memo is None:
            return compute()
        if key not in memo:
            memo[key] = compute()
        return memo[key]

    def _make_directed(self):
        """Turn an undirected graph without links into a directed one, keeping its nodes."""
        if self.directed:
            return
        if self._edge_count:
            raise TarecoError("this graph already has links without direction; to add directed "
                              "ones, start it with tareco.Graph(directed=True)")
        nodes = self._nodes
        self._reset(True)
        for n, d in nodes.items():
            self._add_node(n, d)

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

    def add_links(self, data, source=None, target=None, *, kind=None, directed=None, keep=None,
                  account=None, counterparty=None, amount=None, source_kind=None, target_kind=None,
                  nodes=None, node_id=None, max_rows=1_000_000, skip=None):
        """Add one more table of links, usually of another kind, and return the graph.

        >>> g = tareco.Graph(statements, account="account", counterparty="counterparty", kind="transfer")
        >>> g.add_links(logins, source="account", target="device", kind="uses")

        The node kinds come from the column names ("account", "device") unless
        ``source_kind``/``target_kind`` say otherwise. Links between two different
        kinds of node have no direction unless ``directed=True``; links between
        nodes of one kind follow the graph. Ids of different kinds that clash get
        a prefix ("device:123") and a warning.
        """
        from .io import add_links
        add_links(self, data, source=source, target=target, directed=directed, nodes=nodes,
                  node_id=node_id, max_rows=max_rows, kind=kind, keep=keep, account=account,
                  counterparty=counterparty, amount=amount, source_kind=source_kind,
                  target_kind=target_kind, skip=skip)
        return self

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
        if self._events:
            pair = {(u, v)} if self.directed else {(u, v), (v, u)}
            self._events = [e for e in self._events if (e[0], e[1]) not in pair]

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

    def top_neighbors(self, node, n=5, weight="weight"):
        """The neighbors ``node`` is most strongly connected to, as ``[(neighbor, weight), ...]``.

        "Who buys X also buys", "who talks most to Ana": the heaviest edges first.
        """
        self._check(node)
        wt = _weight_fn(weight, self)
        pairs = {}
        for other, d in self._succ[node].items():
            pairs[other] = pairs.get(other, 0) + wt(d)
        if self.directed:
            for other, d in self._pred[node].items():
                pairs[other] = pairs.get(other, 0) + wt(d)
        pairs.pop(node, None)
        return sorted(pairs.items(), key=lambda kv: -kv[1])[:n]

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
        wt = _weight_fn(weight, self)
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
        # a dict, not a set: the order must not change from one run to the next
        return (self._succ[node] | self._pred[node]).keys()

    # -------------------------------------------------------------- transforms

    def copy(self):
        g = self._new(self.directed)
        for n, d in self._nodes.items():
            g._add_node(n, dict(d))
        for u, v, d in self._edge_triples():
            g._add_edge(u, v, dict(d))
        g._events = list(self._events)
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
        g._events = [e for e in self._events if e[0] in keep_set and e[1] in keep_set]
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
        g._events = [(v, u, k, r) for u, v, k, r in self._events]
        return g

    def to_undirected(self):
        g = self._new(False)
        for n, d in self._nodes.items():
            g._add_node(n, dict(d))
        for u, v, d in self._edge_triples():
            g._add_edge(u, v, dict(d))
        g._events = list(self._events)
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
        g._events = list(self._events)
        return g

    # ------------------------------------------------------------------- kinds

    def kinds(self):
        """How many links and nodes of each kind: ``{"links": {...}, "nodes": {...}}``."""
        from .io import _kinds_of
        links, nodes = {}, {}
        for _, _, d in self._edge_triples():
            for k in _kinds_of(d):
                links[k] = links.get(k, 0) + 1
        for d in self._nodes.values():
            k = d.get("kind")
            if k is not None:
                nodes[k] = nodes.get(k, 0) + 1
        return {"links": links, "nodes": nodes}

    def only(self, *kinds):
        """A copy with just the links of these kinds and the nodes they touch.

        ``g.only("transfer")`` leaves the logins out; ``None`` stands for links
        loaded without a kind.
        """
        from .io import _kinds_of
        wanted = set(kinds)
        g = self._new(self.directed)
        if "link_kinds" in g.attrs:
            g.attrs["link_kinds"] = {k: v for k, v in g.attrs["link_kinds"].items() if k in wanted}
        for u, v, d in self._edge_triples():
            if wanted & (set(_kinds_of(d)) or {None}):
                for x in (u, v):
                    if x not in g._nodes:
                        g._add_node(x, dict(self._nodes[x]))
                g._add_edge(u, v, dict(d))
        g._events = [e for e in self._events if e[2] in wanted]
        return g

    def rows(self, nodes=None, link=None, kind=None):
        """The rows behind the links, as they were in your table (needs ``keep=`` when loading).

        ``nodes`` (one or several) keeps the rows that touch them, ``link=(a, b)``
        the rows behind one link, ``kind`` the rows of one kind of link.
        ``.to_pandas()`` turns the result into a DataFrame.
        """
        from .tracing import Rows
        if not self.attrs.get("kept"):
            raise TarecoError("this graph does not keep the rows behind its links; load it with "
                              "keep=True, or keep=[\"transaction_id\", ...] for some columns")
        events = self._events
        if nodes is not None:
            wanted = set(nodes) if isinstance(nodes, (list, set, frozenset)) else {nodes}
            events = [e for e in events if e[0] in wanted or e[1] in wanted]
        if link is not None:
            a, b = link
            pairs = {(a, b)} if self.directed else {(a, b), (b, a)}
            events = [e for e in events if (e[0], e[1]) in pairs]
        if kind is not None:
            events = [e for e in events if e[2] == kind]
        return Rows(dict(e[3]) for e in events)

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
        found = self._cached(("pagerank", alpha, weight), lambda: pagerank(self, alpha=alpha, weight=weight))
        return dict(found)

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
        found = self._cached(("communities", weight, resolution, seed),
                             lambda: louvain(self, weight=weight, resolution=resolution, seed=seed))
        return [set(c) for c in found]

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

    def find_cycle(self):
        """One cycle as a list of nodes, or None. Any length, including a <-> b."""
        from .algorithms.structure import find_cycle
        return find_cycle(self)

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
        with self._memoized():
            return explain(self, groups=groups, lang=lang, top=top, label=label, weight=weight)

    def profile(self, groups=None, attrs=None, top=3, lang=None, label=None):
        """What characterizes each group (communities by default) compared with the whole network."""
        from .insights import profile
        return profile(self, groups=groups, attrs=attrs, top=top, lang=lang, label=label)

    def project(self, nodes, via=None, method="count", min_shared=1, max_item_size=1000):
        """Link ``nodes`` that share neighbors, like customers who share products.

        ``nodes`` is the side to keep: a node kind ("account"), an iterable of
        nodes, or a predicate on ``(node, attrs)``. ``via`` limits what they share
        to one or more node kinds ("device"). See ``tareco.project`` for the methods.

        >>> g.project("account", via="device")   # accounts linked by the devices they share
        """
        from .bipartite import project_graph
        return project_graph(self, nodes, via=via, method=method, min_shared=min_shared,
                             max_item_size=max_item_size)

    def patterns(self, kinds=None, lang=None, limit=10, weight="weight", max_cycle=None, label=None,
                 min_fan=None):
        """Shapes worth a look: loops, fan-ins and fan-outs, relays, chains, stars, cliques.

        Each pattern has ``kind``, ``nodes``, ``score`` and a plain-language ``text``.
        Loops, fans, relays and chains need a directed graph.
        """
        from .patterns import find_patterns
        return find_patterns(self, kinds=kinds, lang=lang, limit=limit, weight=weight,
                             max_cycle=max_cycle, label=label, min_fan=min_fan)

    def unusual_amounts(self, factor=None, min_history=None, time=None, lang=None, label=None, limit=10):
        """Transfers far above what the sender usually sends (needs ``keep=``).

        ``factor`` times the sender's usual amount, and among the largest 5% of
        the network. Each result has the ``rows`` of your table behind it.
        """
        from .indicators import unusual_amounts
        return unusual_amounts(self, factor=factor, min_history=min_history, time=time, lang=lang,
                               label=label, limit=limit)

    def splits(self, limit=None, within=None, min_count=None, margin=None, time=None, lang=None,
               label=None, top=10):
        """Many amounts just under a limit in a short time, by one sender or into one receiver.

        >>> g.splits(limit=10_000, within="7 days")

        Without ``limit``, amounts piling up just under any round number count.
        Needs ``keep=`` and a date column. See ``tareco.indicators.splits``.
        """
        from .indicators import splits
        return splits(self, limit=limit, within=within, min_count=min_count, margin=margin, time=time,
                      lang=lang, label=label, top=top)

    def fast_moves(self, within=None, share=None, time=None, lang=None, label=None, limit=10):
        """Nodes that receive a large amount and pass most of it on to others within a short time.

        >>> g.fast_moves(within="3 days")
        """
        from .indicators import fast_moves
        return fast_moves(self, within=within, share=share, time=time, lang=lang, label=label, limit=limit)

    def trace(self, source, target=None, within="30 days", hops=4, time=None, lang=None, label=None, limit=10):
        """Where money from ``source`` could have gone, following transfers in time order (needs ``keep=``).

        >>> g.trace("x01", "abroad")          # the paths from x01 to abroad
        >>> g.trace("x01", within="7 days")   # everyone reached within a week
        """
        from .indicators import trace
        return trace(self, source, target, within=within, hops=hops, time=time, lang=lang, label=label,
                     limit=limit)

    def entities(self, via=None, max_share=None, lang=None, label=None):
        """Groups of nodes tied by identifiers they share (devices, phones, addresses): probably one person.

        >>> people = g.entities(via="device")
        >>> people.graph().review()           # the same questions, per person

        Identifiers shared by more than ``max_share`` nodes tie nothing.
        """
        from .entities import entities
        return entities(self, via=via, max_share=max_share, lang=lang, label=label)

    def misfits(self, attrs=None, factor=None, min_neighbors=None, lang=None, label=None, limit=10):
        """Nodes unlike the ones they deal with: a far lower or higher number, a rare category.

        >>> g.misfits("monthly_income")
        """
        from .indicators import misfits
        return misfits(self, attrs=attrs, factor=factor, min_neighbors=min_neighbors, lang=lang,
                       label=label, limit=limit)

    def near(self, targets, hops=None, lang=None, label=None, limit=10, kinds=None):
        """Nodes within ``hops`` steps of a list you give, and through whom (paths skip hubs).

        >>> g.near(["a017", "a020"])          # or an attribute: g.near("flagged")
        """
        from .indicators import near
        return near(self, targets, hops=hops, lang=lang, label=label, limit=limit, kinds=kinds)

    def flows(self, by, direction="to", weight="weight", lang=None, label=None):
        """How much of the flow goes to each value of an attribute (a country, a segment).

        >>> g.flows(by="country")
        """
        from .indicators import flows
        return flows(self, by, direction=direction, weight=weight, lang=lang, label=label)

    def why(self, node, watch=None, lang=None, label=None):
        """What stands out about one node, in plain words: its flows, group, patterns,
        unusual amounts, what it shares with others and, with ``watch``, how close
        it is to a list you give."""
        from .investigate import why
        with self._memoized():
            return why(self, node, watch=watch, lang=lang, label=label)

    def review(self, watch=None, limit=None, within=None, top=50, lang=None, label=None):
        """Every node something stands out about, ranked, with its reasons and the rows behind them.

        >>> g.review(watch=["a017"]).to_pandas()     # a work list for whoever investigates
        """
        from .review import review
        with self._memoized():
            return review(self, watch=watch, limit=limit, within=within, top=top, lang=lang, label=label)

    def similar_to(self, nodes, n=10, lang=None, label=None):
        """The nodes that behave most like ``nodes`` (one or a few known cases), with the reasons.

        >>> g.similar_to("a017").nodes        # ids to look up in your own tables
        """
        from .investigate import similar_to
        with self._memoized():
            return similar_to(self, nodes, n=n, lang=lang, label=label)

    def compare(self, after, lang=None, label=None, top=3):
        """What changed from this graph to ``after`` (another month, region, version), in words."""
        from .compare import compare
        return compare(self, after, lang=lang, label=label, top=top)

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
        """Write the interactive view to a standalone HTML file, a picture for ``.svg``/``.png``,
        or the whole graph for ``.tareco``.

        Pictures are drawn in Python, for slides and e-mails: ``color``, ``size``,
        ``label``, ``title``, ``width``, ``height``, ``theme`` ("light", "dark"),
        ``labels`` (how many names to write) and ``max_nodes``. PNG needs Pillow.

        A ``.tareco`` file keeps everything, the rows behind the links included,
        to pick the investigation up later with ``tareco.load(path)``.
        """
        import os
        ext = os.path.splitext(str(path))[1].lower()
        if ext == ".tareco":
            if options:
                raise TarecoError(f"a .tareco file keeps the whole graph; {sorted(options)} do not apply")
            from .case import save
            return save(self, path)
        if ext == ".svg":
            from .picture import to_svg
            with open(path, "w", encoding="utf-8") as f:
                f.write(to_svg(self, **options))
            return os.path.abspath(path)
        if ext == ".png":
            from .picture import to_png
            to_png(self, path, **options)
            return os.path.abspath(path)
        from .viz import save
        return save(self, path, **options)

    def to_svg(self, **options):
        """A still picture of the graph as SVG text (see ``save``)."""
        from .picture import to_svg
        return to_svg(self, **options)

    def report(self, path=None, title=None, lang=None, label=None, **view):
        """A single HTML file with the findings, group and node tables, and the graph.

        Made to be sent to someone. Returns the path, or the HTML when ``path`` is None.
        """
        from .report import report
        with self._memoized():
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


def _resolve_weight(g, weight):
    """The graph's own weight column stands in for the default name "weight"."""
    if weight == "weight" and g is not None:
        return g.attrs.get("weight") or weight
    return weight


def _weight_fn(weight, g=None):
    """``attrs -> number`` for an edge attribute name; missing values count as 1."""
    weight = _resolve_weight(g, weight)
    if weight is None:
        return lambda d: 1
    return lambda d: d.get(weight, 1)

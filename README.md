# tareco

**Graphs made simple.** Hand it a CSV, a DataFrame or a list of pairs and get a
beautiful interactive graph you can drag, search and click through. Then ask it
real questions: who matters most, who bridges groups, which communities exist,
what is the shortest route.

No dependencies. Every algorithm is written from scratch in pure Python, and
the view is a single self-contained HTML file that works offline.

![tareco interactive view](https://raw.githubusercontent.com/naruminho/tareco/master/docs/screenshot.jpg)

```bash
pip install tareco
```

## One line

```python
import tareco

tareco.show("friends.csv")
```

That's it. Columns named `from`/`to`, `source`/`target`, `origem`/`destino`
(and friends) are found on their own, otherwise the first two columns are used.
Every other column becomes an edge attribute. Nodes are colored by community
and sized by importance automatically.

It also takes whatever you already have:

```python
tareco.show([("ana", "bia"), ("bia", "caio", 3.5)])          # pairs, optional weight
tareco.show({"ana": ["bia", "caio"], "bia": ["davi"]})       # dict of neighbors
tareco.show(df)                                              # pandas or polars DataFrame
tareco.show(spark_df)                                        # Spark DataFrame
tareco.show("friends.csv", nodes="people.csv")               # node attributes too
tareco.show(df, source="sender", target="receiver", directed=True)
```

From the terminal:

```bash
tareco friends.csv --nodes people.csv --color city
tareco transfers.csv --directed --max-nodes 20000 -o transfers.html
```

## The view

- **Hover** a node to light up its neighborhood; **click** it for a side panel
  with its metrics, attributes and clickable neighbors.
- **Drag** nodes around; dragged nodes stay pinned (right-click to release).
- **Search** with `/`, jump with Enter.
- **Shortest path** mode: click two nodes and the route lights up.
- **Legend** filters: click a group to hide it, double-click to see only it.
- Freeze the layout, toggle labels, switch dark/light, save a PNG.
- Directed graphs get arrows; `particles=True` animates the flow.
- `dim=3` gives you a 3D graph you can orbit.

```python
g.show(
    color="city",            # attribute or metric: "community", "pagerank", "degree",
                             # "betweenness", "closeness", "clustering", "core", "component"
    size="betweenness",      # same options, numbers only
    label="name",            # attribute to display instead of the id
    edge_width="messages",   # defaults to "weight" when edges have one
    title="Friends",
    theme="dark",            # "auto", "dark", "light"
)
g.save("friends.html")       # standalone file, send it to anyone
```

`color` and `size` also accept a `{node: value}` dict (like the output of any
algorithm), a function of the node, or a fixed CSS color.

## Notebooks and Databricks

In Jupyter, VS Code, Colab and Databricks, `g.show()` draws the graph right in
the cell, and so does leaving a graph as the last line of a cell. On Databricks
it goes through `displayHTML`. Where there is neither a notebook nor a browser
(a cluster job, a server), the page is saved to a temporary file and its path is
printed.

Notebook output is kept under a size budget, because big outputs get cut:
Databricks truncates cell output at 10 MB by default (DBR 17+). If a graph does
not fit, tareco keeps its most important part and says so in the header
(`48,000 of 1,200,000 nodes`). Pass `budget_mb=` to change it; on Databricks,
`%set_cell_max_output_size_in_mb 20` raises the limit.

## Spark

```python
from pyspark.sql import functions as F

transfers = spark.table("payments.transfers")   # from_account, to_account, amount, ...

edges = (transfers
         .groupBy("from_account", "to_account")
         .agg(F.sum("amount").alias("weight"), F.count("*").alias("count")))

g = tareco.Graph(edges, source="from_account", target="to_account", directed=True)
g.show(title="Transfers")
```

A Spark DataFrame is streamed to the driver one partition at a time (no pandas
needed), and `DECIMAL` columns become floats. Anything above `max_rows` rows
(1,000,000 by default) is refused with a hint to aggregate in Spark first, which
is almost always the right move: a graph of who-pays-whom with a total per pair
is far smaller than the raw transactions. `max_rows=None` lifts the limit.

## Big graphs

Tens of thousands of nodes are fine. The view changes strategy as the graph grows:

- **Up to 2,000 nodes / 8,000 edges:** the canvas view above, animated.
- **Bigger:** a WebGL view (sigma.js). The layout runs in a background
  worker, so the page never freezes while it settles, and edges fade with
  density so structure shows instead of a white blob. Nodes are pulled toward
  their community, so groups read as islands.
- **Group overview:** every community (or every value of a categorical `color`)
  becomes one bubble, sized by members and linked by how much they interact.
  Click a bubble to open just that group; very big graphs open here first.
- **Trimming:** past `max_nodes` (50,000) or `max_edges` (200,000), only the
  most important nodes (by PageRank) and the heaviest edges are embedded. The
  overview still counts everything.

```python
g.show(renderer="webgl")              # force a renderer: "auto", "canvas", "webgl"
g.show(max_nodes=20_000)              # embed less (smaller, faster page)
g.betweenness(k=500)                  # estimate from 500 sources instead of all nodes
```

Community detection handles 50,000 nodes and 200,000 edges in about two
seconds, in pure Python.

## The graph

```python
g = tareco.Graph("friends.csv", nodes="people.csv")

g.add_edge("Ana", "Zeca", weight=2, since=2019)
g.add_node("Zeca", city="Recife")

g.nodes["Ana"]              # {'city': 'Recife', 'age': 31}
g.edges["Ana", "Bia"]       # {'messages': 42}
g.neighbors("Ana")          # ['Bia', 'Caio', 'Duda', 'Pedro', 'Zeca']
g.degree("Ana")             # 5
len(g), g.edge_count        # (17, 32)

g.subgraph(["Ana", "Bia", "Caio"])
g.ego("Ana", radius=2)       # everyone within two steps
g.reverse(), g.to_undirected(), g.copy()
```

## The questions

| Ask | Method |
| --- | --- |
| Overview | `g.summary()` |
| Shortest route | `g.shortest_path(a, b, weight=None)`, `g.distance(a, b)`, `g.distances(a)` |
| Who is important | `g.pagerank()`, `g.degree_centrality()` |
| Who bridges groups | `g.betweenness(k=None)` (`k` sources estimate it fast) |
| Who is close to everyone | `g.closeness()` |
| Which groups exist | `g.communities()` (Louvain), `g.modularity(groups)` |
| Are they connected | `g.components()`, `g.strong_components()`, `g.is_connected()` |
| How tight is it | `g.clustering()`, `g.triangles()`, `g.transitivity()`, `g.density()` |
| The core | `g.core_number()`, `g.k_core(k)` |
| Who should meet | `g.suggest_links(node=None, top=10)` (Adamic-Adar) |
| Cheapest wiring | `g.spanning_tree(weight="weight")` |
| Order of tasks | `g.topological_sort()`, `g.has_cycle()` |
| Size of the world | `g.diameter()` |
| Walk it | `g.bfs(a)`, `g.dfs(a)` |

Results are plain dicts, lists and sets. Pass `weight="some_attribute"` to use
edge weights. The algorithms are tested against networkx and give the same
numbers.

## Ready-made graphs

```python
tareco.community_graph([30, 20, 10])   # planted groups, great for testing communities()
tareco.scale_free_graph(500, 2)        # a few big hubs, like the web
tareco.small_world_graph(100, 4, 0.1)  # ring with shortcuts
tareco.random_graph(100, 0.05)
tareco.grid_graph(10, 10), tareco.complete_graph(8), tareco.star_graph(6)
tareco.path_graph(5), tareco.cycle_graph(5)
```

## In and out

```python
g.to_csv("edges.csv", "nodes.csv")    tareco.read_csv("edges.csv", "nodes.csv")
g.to_json("graph.json")               tareco.read_json("graph.json")
nodes_df, edges_df = g.to_pandas()    tareco.Graph(df, nodes=nodes_df)
g.to_networkx()                       tareco.Graph(nx_graph)
```

CSV files may use `,` `;` `\t` or `|`, and `1,5`-style decimals are understood.

## Development

```bash
pip install -e ".[test]"
pytest
```

The interactive views are drawn with
[force-graph](https://github.com/vasturiano/force-graph),
[sigma.js](https://www.sigmajs.org) and [graphology](https://graphology.github.io)
(all MIT), bundled inside the package so pages work offline. The 3D view loads
[3d-force-graph](https://github.com/vasturiano/3d-force-graph) from a CDN.

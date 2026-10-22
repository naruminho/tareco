# A tareco guide for people who never used graphs

This guide starts from zero. If you can open a CSV in Python, you can use tareco.

- [What a graph is](#what-a-graph-is)
- [Install](#install)
- [Your first graph](#your-first-graph)
- [What the table should look like](#what-the-table-should-look-like)
- [Where the data can come from](#where-the-data-can-come-from)
- [Reading the page](#reading-the-page)
- [Question, method](#question-method)
- [The summary in words](#the-summary-in-words)
- [Over time](#over-time)
- [Two-sided data](#two-sided-data)
- [Several kinds of links](#several-kinds-of-links)
- [Money and investigations](#money-and-investigations)
- [Huge tables, Spark and Databricks](#huge-tables-spark-and-databricks)
- [When something goes wrong](#when-something-goes-wrong)
- [Glossary](#glossary)

## What a graph is

A graph is a network: **things** and **links between them**.

| Things (nodes) | Links | Typical question |
| --- | --- | --- |
| people | friendships, e-mails, meetings | who bridges the departments? |
| accounts | money transfers | is money going around in circles? |
| customers | products bought in common | what kinds of customer are there? |
| stations | subway stretches | what is the fastest way? |
| packages, tasks | "depends on" | in what order should things be done? |
| factories, stores | delivery routes | where is the bottleneck? |

When the question is about **relationships** (who is linked to whom, what goes
through where, who sits in the middle, which groups form), a plain table
struggles to answer and a graph does it well.

## Install

```bash
pip install tareco
```

Nothing else is needed. pandas, polars and Spark work if you already have them,
but none of them is required.

## Your first graph

A table, `friends.csv`:

```
from,to
Ana,Bia
Ana,Caio
Bia,Caio
Caio,Davi
```

One line of code:

```python
import tareco

tareco.show("friends.csv")
```

A page opens in the browser (or inside the notebook) with the network: you can
drag, search and click. The colors are the groups tareco found and the size is
how important each node is.

To ask questions, load it into a `Graph`:

```python
g = tareco.Graph("friends.csv")
print(g.explain())                      # what the network shows, in words
g.shortest_path("Ana", "Davi")          # ['Ana', 'Caio', 'Davi']
g.save("friends.html")                  # the page, to send to someone
```

The sentences come out in your computer's language (English or Portuguese). To
fix them to English: `tareco.set_language("en")`.

## What the table should look like

**One row per link.** One column with where it starts, another with where it
ends. Every other column becomes information about the link.

tareco recognizes these names on its own:

| Role | Names it recognizes |
| --- | --- |
| start | `source`, `from`, `src`, `origin`, `sender`, `start`, `parent` (and `origem`, `de`) |
| end | `target`, `to`, `dst`, `destination`, `dest`, `receiver`, `end`, `child` (and `destino`, `para`) |
| weight | `weight`, `value`, `amount`, `quantity`, `count`, `total` (and `peso`, `valor`, `quantidade`...) |

With other names, say which is which:

```python
g = tareco.Graph("payments.csv", source="payer", target="payee", weight="paid")
```

If you don't, and no name matches, tareco uses the first two columns and
**warns** you which ones it picked (a `GuessWarning`). Read the warning: if the
columns are wrong, pass `source=` and `target=`.

**Direction.** By default a link goes both ways (friendship, contact). When it
has a direction (payment, e-mail sent, "depends on"), use `directed=True`.

**Repeated rows** between the same two ends become a single link: number columns
are added up and a `count` column says how many rows there were. Ten transfers
from Ana to Bia become one link with the total amount and `count=10`.

**The weight** says how strong a link is (amount, number of messages, minutes).
It is used in the summary, in the width of the lines and when you pass
`weight="weight"` to the algorithms. tareco picks it by itself: a column with
one of the names above, or else the only number column (like `messages` or
`minutes`; ids, years and dates do not count), or else the `count` of repeated
rows. To pick another one: `weight="column_name"`.

**A table of nodes (optional).** A second table, one row per node, with what you
know about each one (city, department, segment). This is what makes the summary
interesting: "Group 1: city Recife in 75%".

```python
g = tareco.Graph("friends.csv", nodes="people.csv")
```

The column that identifies the node is recognized by names like `id`, `name`,
`account`, `customer`, `user`, `person`, `code`; otherwise the first column is
used. To choose: `node_id="employee_number"`.

## Where the data can come from

All of these work in `tareco.Graph(...)`, `tareco.show(...)` and the other functions:

```python
tareco.Graph("data.csv")                  # CSV with , ; tab or |, and 1,5-style decimals
tareco.Graph("data.xlsx")                 # Excel (first sheet), no pandas needed
tareco.read_excel("data.xlsx", sheet="sales")   # another sheet
tareco.Graph("graph.json")
tareco.Graph(df)                          # pandas or polars
tareco.Graph(spark.table("table"))        # Spark
tareco.Graph([("Ana", "Bia"), ("Bia", "Caio", 3)])   # a list of pairs (weight optional)
tareco.Graph({"Ana": ["Bia", "Caio"]})              # a dict of neighbors
```

And from the terminal, without writing code:

```bash
tareco friends.csv --nodes people.csv --explain
```

## Reading the page

- **Hover** a node: it and its neighbors light up.
- **Click** a node: a card opens with what stands out about it, its metrics, attributes and (clickable) neighbors.
- **Drag** a node: it stays where you drop it. Right-click lets it go.
- **Search** (the `/` key): type a name and press Enter.
- **Insights**: the sentences of the summary. Click one to light up the nodes it talks about; with rows kept, the rows of your table behind it show up too.
- **Shortest path**: click two nodes and the path between them lights up.
- **Legend**: one click hides a group, a double click shows only that group.
- **Groups overview**: each group becomes a bubble; click one to open it.
- **Time slider** (when there are dates): drag it or press Play.
- Buttons to fit the view, toggle labels, freeze the layout, switch light/dark and save an image.

Choosing what the page shows:

```python
g.show(color="city",             # color by an attribute, or "community", "pagerank"...
       size="betweenness",       # size by a metric
       label="name",             # what is written next to each node
       edge_width="amount",      # line width
       title="My network")
```

For a slide or an e-mail, save a still picture instead of a page:

```python
g.save("network.svg", color="city", title="My network")   # nothing else needed
g.save("network.png", color="city")                        # needs Pillow: pip install pillow
```

Big graphs (thousands of nodes) switch to WebGL on their own, which handles
tens of thousands without freezing.

## Question, method

| You want to know | Use |
| --- | --- |
| What the network shows, in words | `g.explain()` |
| Which groups exist and what sets each apart | `g.profile()`, `g.communities()` |
| How each department (or any attribute) relates to the others | `g.profile(groups="department")` |
| Who is most important | `g.pagerank()` |
| Who bridges, what most paths go through | `g.betweenness()` |
| Who has the most links | `g.degree(node)`, `g.degree_centrality()` |
| Whom someone relates to most | `g.top_neighbors(node, n=5)` |
| The path between two nodes | `g.shortest_path(a, b)`; the cheapest: `weight="weight"` |
| Alternative paths | `g.k_shortest_paths(a, b, k=3)` |
| How much can flow, and the bottleneck | `g.max_flow(a, b, capacity="capacity")` |
| Who should meet | `g.suggest_links(top=10)` |
| Shapes worth a look (loops, collectors, chains) | `g.patterns()` |
| Is there a cycle? Which one? | `g.has_cycle()`, `g.find_cycle()` |
| In what order to do things | `g.topological_sort()` |
| Everything reachable from a node | `g.bfs(node)` |
| Is the network split? | `g.components()` |
| Just the surroundings of someone | `g.ego(node, radius=2)` |
| A report to send | `g.report("report.html")` |
| The results in a table | `g.to_pandas(metrics=["pagerank", "community"])` |

Results are plain Python dicts and lists:

```python
rank = g.pagerank()                                    # {'Ana': 0.31, 'Bia': 0.22, ...}
top3 = sorted(rank.items(), key=lambda kv: -kv[1])[:3] # the 3 highest
```

To change the graph: `g.add_edge(a, b, amount=10)`, `g.remove_node(x)`,
`g.copy()`, `g.reverse()` (flips the arrows), `g.subgraph([...])`.

## The summary in words

`explain()` is the best way to start on a network you don't know:

```python
print(g.explain())
```

It says whether the network is split, which groups exist **and what sets each
one apart** (attributes much more common in the group than overall), who is
important, who bridges, who concentrates links, patterns worth a look and how
concentrated the weight is. Each sentence also keeps the nodes it talks about:

```python
for finding in g.explain():
    print(finding.text, finding.nodes)
```

- `g.profile()`: the full card of each group.
- `g.patterns()`: the shapes, one by one (loop, many to one, one to many,
  relay, chain, back and forth, star, clique).
- `g.report("file.html")`: all of it in one page, with tables and the graph.
- `tareco.explain("data.csv")` and `tareco.report("data.csv", "out.html")` do the
  same straight from the file.

A pattern is a place to start looking, not a verdict.
[Recipe 02](../examples/recipes/02-transfers/) shows the difference.

## Over time

If every row has a date, the network becomes a timeline:

```python
timeline = tareco.timeline("emails.csv", time="date")
print(timeline.explain())    # what changed: who showed up, who jumped, new groups
timeline.show()              # the page with a time slider
timeline["2026-04"]          # the network of a single period
timeline.union               # every period together
timeline.spread("Ana")       # who could have heard something from Ana, in time order
```

Dates can be dates, text like `2026-04-15` or `15/04/2026`, or numbers. tareco
picks days, weeks, months, quarters or years on its own; to choose,
`freq="month"`.

To put two moments side by side:

```python
timeline.compare("2026-01", "2026-06")     # two periods of a timeline
tareco.compare(january, june)              # any two graphs: regions, versions, before and after
```

It says which nodes came and went, who rose in importance or jumped in
connections, which groups formed, vanished or merged, and which links grew most.

## Two-sided data

Sometimes the table does not say who is linked to whom, but "customer bought
product", "student took course", "account used device". The projection links
the customers who bought the same things:

```python
customers = tareco.project(purchases, nodes="customer", via="product", method="newman")
```

`method="newman"` makes products everybody buys count for little. See
[recipe 04](../examples/recipes/04-shopping/).

## Several kinds of links

Real data mixes things: accounts and the devices they log in from, people and
their addresses. Load each table as links of its own kind:

```python
g = tareco.Graph(transfers, kind="transfer", directed=True)
g.add_links(logins, source="account", target="device", kind="uses")
g.kinds()                    # how many links and nodes of each kind
g.only("transfer")           # just one kind
```

The kind of each node comes from the column name (`account`, `device`). A login
has no direction and carries no money, so it does not count as a flow, but it
still ties accounts together: "4 account nodes share dev-77 (device)".

## Money and investigations

A bank statement has one row per entry and money out negative. Tell tareco which
columns are the two sides:

```python
g = tareco.Graph(statements, account="account", counterparty="counterparty",
                 kind="transfer", keep=True)
```

| You want to know | Use |
| --- | --- |
| Many amounts just under a limit, in a few days | `g.splits(limit=10_000, within="7 days")` |
| Amounts far above what the account usually sends | `g.unusual_amounts()` |
| Where the money goes (by country, by segment) | `g.flows(by="country")` |
| Who does not fit with the people they deal with | `g.misfits("income")` |
| Who is close to accounts you already know | `g.near(["a017"])` |
| Everything about one account | `g.why("a023")` |
| Others that behave like a known case | `g.similar_to("a017")` |
| The transactions behind a finding | `finding.rows`, `g.rows("a017")` |
| The same accounts in your own table | `tareco.records(table, ids, columns=["account"])` |
| A large amount in and out again within days | `g.fast_moves(within="3 days")` |
| Where the money from one account went, in time order | `g.trace("a181", "PI-ACC-8")` |
| Several accounts that are probably one person | `g.entities(via="device")` |
| All of it, per account, ranked: a work list | `g.review(watch=["a017"])` |

`g.review()` is the place to start a day of work: it ranks the accounts by how
many signals they have and how strong, gives one line per kind of signal and the
ids of the transactions behind them. `review.to_pandas()` or
`review.to_spark(spark)` turns it into a table to save next to the data.
`g.entities(via="device").graph()` merges the accounts each person uses into one
node, and every question then runs per person.

`keep=True` is what lets tareco look at single transfers and take you back to
them. The limits and the lists are yours: tareco says what it sees, you decide
what is a problem. [Recipe 09](../examples/recipes/09-statements/) walks through
all of it.

## Huge tables, Spark and Databricks

- tareco reads a Spark DataFrame directly: `tareco.Graph(spark.table("t"))`. The
  rows come over a bit at a time, without pandas.
- Above 1 million rows it refuses and suggests **aggregating in Spark first**:
  one row per pair, with the sum. That is almost always the right move.
  (`max_rows=None` lifts the limit.)
- To look into one account in a huge table, `tareco.neighborhood(table,
  start="account", hops=2)` fetches only its surroundings, inside the cluster.
- To ask the whole table without bringing it over, `tareco.big` computes inside
  Spark and returns Spark tables: `tareco.big.components(edges)`,
  `degrees`, `pagerank`, `communities`, and `statement_edges(statements, ...)`
  to turn bank statements into edges first.
- On Databricks, `g.show()` draws inside the cell. If the graph does not fit in
  the cell's output limit, tareco shows its most important part and says so.
- `tareco.doctor(spark)` checks that everything works in the environment. There
  is a ready notebook in [examples/databricks_check.py](../examples/databricks_check.py).

## When something goes wrong

**"no column looks like the source, so 'x' was used"**
tareco did not find the start column by its name and took a guess. Pass
`source="column"` and `target="column"`. If the guess is right and the warning
bothers you: `warnings.filterwarnings("ignore", category=tareco.GuessWarning)`.

**The arrows point the wrong way**
Swap `source` and `target`, or use `g.reverse()`.

**`tareco.NoPath: no path from 'A' to 'B'`**
There is no path. In directed graphs there may be one from B to A and none from
A to B. See the parts of the network with `g.components()`. To handle it in code:

```python
try:
    g.shortest_path("A", "B")
except tareco.NoPath:
    print("no path")
```

**`tareco.NodeNotFound: node 'X' is not in the graph`**
There is no node with that exact name. Check upper case, spaces, and whether the
code came in as a number (`123`) or as text (`"123"`): `"123" in g`.

**In the projection, everybody got linked to everybody**
Some item is bought by almost everyone. Use `method="newman"`, or lower
`max_item_size`.

**The weight is not the column I wanted**
Say which one: `tareco.Graph(..., weight="minutes")`. To ignore the weight in an
algorithm, don't pass `weight`.

**An `.xls` file (old Excel)**
Save it as `.xlsx` in Excel, or read it with pandas.

**The sentences are in Portuguese**
Your computer is set to Portuguese. `tareco.set_language("en")`, or the
environment variable `TARECO_LANG=en`.

**"this needs the single rows behind each link; load the graph with keep=True"**
`splits`, `unusual_amounts` and `rows` look at single transfers. Load the graph
with `keep=True`.

**The page got heavy**
`g.show(max_nodes=5000)` shows only the most important nodes. Huge graphs open
on the groups overview.

## Glossary

- **Node** (or vertex): one of the things in the network. A person, an account, a station.
- **Link** (or edge, connection): the relationship between two nodes.
- **Weight**: how strong a link is, or what it costs (amount, messages, minutes).
- **Directed**: the link goes from one node to the other, like an arrow.
- **Degree**: how many links a node has.
- **Neighbors**: the nodes linked directly to a node.
- **Group** (community): nodes that link to each other much more than to the rest.
- **Bridge**: a node that links different groups.
- **PageRank**: how important a node is, counting links from important nodes as worth more.
- **Betweenness**: in how many shortest paths a node sits in the middle. High
  means bridge, bottleneck, point of failure.
- **Closeness**: how near a node is to everyone else.
- **Component**: a part of the network cut off from the others.
- **Shortest path**: the path with the fewest steps, or the cheapest one when there is a weight.
- **Cycle** (loop): a path that comes back to where it started.
- **Clique**: a group in which everyone is linked to everyone.
- **Maximum flow**: the most that can get from one point to another, respecting
  each link's capacity.
- **Minimum cut**: the links that limit the maximum flow; the bottleneck.
- **Projection**: turning "customer bought product" into "customer similar to customer".
- **Topological order**: an order in which each item comes before the ones that depend on it.

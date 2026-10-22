# 03. Supply chain: how much can be delivered, and where is the bottleneck?

**The question:** suppliers feed factories, factories ship to distribution
centers (DCs) and the DCs supply the stores. How much can the whole network
deliver each week? Which route limits everything? What if a factory stops?

The same reasoning works for any network with capacity: pipes, power grids,
computer networks, patients moving between hospitals.

## The data

`routes.csv`: one row per route (40 routes).

| from | to | capacity | cost | days |
| --- | --- | --- | --- | --- |
| Supplier A | Factory Central | 600 | 8 | 2 |
| Factory East | DC Southeast | 400 | 4 | 1 |

`capacity` is how much gets through each week, `cost` is the cost per unit and
`days` the lead time.

## Run it

```bash
python examples/recipes/03-supply-chain/supply_chain.py
```

## Step by step

**1. Load.** `from` and `to` are recognized on their own. Routes have a
direction (from the supplier toward the store), so `directed=True`.

```python
routes = tareco.Graph("routes.csv", directed=True)
```

**2. How much reaches the stores?** The **maximum flow** uses each route's
capacity and works out the most that can leave one point and arrive at another.
To measure the whole network (several suppliers, several stores), a common
trick: add a `SOURCE` linked to every supplier and a `SINK` linked to every
store, with capacity to spare.

```python
network = routes.copy()
for s in suppliers:
    network.add_edge("SOURCE", s, capacity=10**9)
for store in stores:
    network.add_edge(store, "SINK", capacity=10**9)
flow = network.max_flow("SOURCE", "SINK", capacity="capacity")
```

```
The network delivers up to 2040 units a week.
The bottleneck is 19 routes; 18 of them are deliveries from DCs to stores.
  and also Factory Central -> DC South (300 a week)
```

`flow.value` is the total. `flow.cut` is the **minimum cut**: the routes that,
added up, limit the delivery. Widening any other route does nothing; this is
where to invest. Here the bottleneck is the last mile (DCs to stores), plus the
route from Factory Central to DC South.

`flow.flows` says how much goes through each route in the best case.

**3. What if a factory stops?** Take the factory out and compute again:

```
Without Factory East, the network loses 740 units a week.
Without Factory Central, the network loses 620 units a week.
Without Factory South, the network loses 100 units a week.
```

Factory South is barely missed: other routes make up for it. Factory East is
the most critical.

**4. The cheapest route, and the alternatives.**

```python
routes.shortest_path("Supplier A", "Store 07", weight="cost")
routes.k_shortest_paths("Supplier A", "Store 07", k=3, weight="cost")
```

```
Cheapest from Supplier A to Store 07 (cost 17): Supplier A -> Factory Central -> DC South -> Store 07
  alternative (cost 20): Supplier A -> Factory Central -> DC Southeast -> Store 07
  alternative (cost 22): Supplier A -> Factory East -> DC Southeast -> Store 07
```

Swap `weight="cost"` for `weight="days"` and the question becomes "what is the
fastest route".

**5. See it.** `out/routes.html`, with the width of each route showing its
capacity (`edge_width="capacity"`).

## What to look at in the page

- Arrows show the direction of each route.
- **Shortest path** button: click a supplier, then a store.
- Click a DC to see where it gets goods from and whom it supplies.

## With your own data

Any table of origin, destination and capacity. The columns can have other
names: `max_flow(..., capacity="column_name")`.

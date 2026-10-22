"""Supply chain: how much can be delivered each week, and where is the bottleneck?

Suppliers feed factories, factories ship to distribution centers (DCs) and the
DCs supply the stores. Every route has a capacity (units per week), a cost per
unit and a lead time in days.

Run from the tareco folder:  python examples/recipes/03-supply-chain/supply_chain.py
"""

from pathlib import Path

import tareco

HERE = Path(__file__).parent
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)

# %% 1. Load
# routes.csv: from, to, capacity, cost, days. "from" and "to" are recognized on
# their own. Routes have a direction (from the supplier toward the store), so directed=True.
routes = tareco.Graph(HERE / "routes.csv", directed=True)
print(routes)
print()

# %% 2. How much reaches the stores?
# Maximum flow uses each route's capacity. To measure the whole network, a common
# trick: one "SOURCE" linked to every supplier and one "SINK" linked to every
# store, with capacity to spare.
suppliers = [n for n in routes if str(n).startswith("Supplier")]
stores = [n for n in routes if str(n).startswith("Store")]
network = routes.copy()
for s in suppliers:
    network.add_edge("SOURCE", s, capacity=10**9)
for store in stores:
    network.add_edge(store, "SINK", capacity=10**9)
flow = network.max_flow("SOURCE", "SINK", capacity="capacity")
print(f"The network delivers up to {flow.value} units a week.")
# The minimum cut: the routes that, added up, limit the delivery. Widening any
# other route does nothing; this is where to invest.
to_stores = [c for c in flow.cut if c[1].startswith("Store")]
print(f"The bottleneck is {len(flow.cut)} routes; {len(to_stores)} of them are deliveries from DCs to stores.")
for start, end, capacity in flow.cut:
    if not end.startswith("Store"):
        print(f"  and also {start} -> {end} ({capacity} a week)")
print()

# %% 3. What if a factory stops?
for factory in ("Factory East", "Factory Central", "Factory South"):
    without = network.copy()
    without.remove_node(factory)
    loss = flow.value - without.max_flow("SOURCE", "SINK", capacity="capacity").value
    print(f"Without {factory}, the network loses {loss} units a week.")
print()

# %% 4. The cheapest route to a store, and the alternatives
path = routes.shortest_path("Supplier A", "Store 07", weight="cost")
cost = routes.distance("Supplier A", "Store 07", weight="cost")
print(f"Cheapest from Supplier A to Store 07 (cost {cost}):", " -> ".join(path))
for alternative in routes.k_shortest_paths("Supplier A", "Store 07", k=3, weight="cost")[1:]:
    cost = sum(routes.edges[a, b]["cost"] for a, b in zip(alternative, alternative[1:]))
    print(f"  alternative (cost {cost}):", " -> ".join(alternative))
print()

# %% 5. See it
# The width of each route shows its capacity.
routes.save(OUT / "routes.html", edge_width="capacity", color="#6366f1", title="Supply routes")
print("Open:", OUT / "routes.html")

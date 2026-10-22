"""Software dependencies: in what order to install, is there a circular dependency, what breaks if X fails?

Each row says that one package depends on another (package -> depends_on).

Run from the tareco folder:  python examples/recipes/06-dependencies/dependencies.py
"""

from pathlib import Path

import tareco

HERE = Path(__file__).parent
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)

# %% 1. Load
# "package" and "depends_on" are not names tareco knows, so we say which is which.
# directed=True: "web-shop depends on api" is not the same as the other way around.
deps = tareco.Graph(HERE / "dependencies.csv", source="package", target="depends_on", directed=True)
print(deps)
print()

# %% 2. Is there a circular dependency?
cycle = deps.find_cycle()
if cycle:
    print("Circular dependency:", " -> ".join(cycle + cycle[:1]))
else:
    print("No circular dependency.")
print()

# %% 3. Install order
# topological_sort puts each package before the ones it points to. Here arrows go
# from a package to what it needs, so we reverse them to install the base first.
# With a cycle no order exists; we drop the edge that closes it to carry on.
no_cycle = deps.copy()
no_cycle.remove_edge("config", "cache")
order = no_cycle.reverse().topological_sort()
print("Install in this order:", ", ".join(order))
print()

# %% 4. What breaks if a package fails?
# Everything that depends on utils, directly or not: follow the arrows backwards.
affected = deps.reverse().bfs("utils")[1:]
print(f"If 'utils' breaks, {len(affected)} packages break with it: {', '.join(affected[:8])}...")
print()

# %% 5. The most critical packages
# PageRank on a dependency graph: the more important things depend on a package,
# the higher it ranks.
critical = sorted(deps.pagerank().items(), key=lambda kv: -kv[1])[:5]
print("Most critical:", ", ".join(name for name, _ in critical))
print()

# %% 6. See it
deps.save(OUT / "dependencies.html", size="pagerank", title="Dependencies")
print("Open:", OUT / "dependencies.html")
